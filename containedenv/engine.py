import docker
from pyrc.system import LocalFileSystem
from pyrc.docker import DockerEngine
from containedenv.dockerfile import UbuntuDockerFile
from containedenv.packages import PackageManager
from containedenv.config import *

#from traitlets import Any, Dict, Int, List, Unicode, Bool, default
#from traitlets.config import Application

class ContainedEnv:

	@property
	def image(self):
		return self._engine.image

	@property
	def container(self):
		return self._engine.container

	@property
	def config(self):
		return self._config

	@property
	def local(self):
		return self.local

	def __init__(self, config:dict) -> None:
		# protected
		self._local = LocalFileSystem()
		self._config = config
		self._engine = DockerEngine(user = user(self._config))
		# public
		self.dockerclient = docker.from_env()

	def home(self) -> str:
		return f"/home/{user(self._config)}"

	def projects(self) -> str:
		return f"{self.home()}/projects"

	def __build_dockerfile(self):
		# Create the dockerfile
		dockerfile = UbuntuDockerFile(
			self._local.join(config_dir(), f"Dockerfile.{appname(self.config)}")
		)
		# install packages
		dockerfile.install(["sudo", "wget", "curl"])

		# create the user workspace
		username = user(self._config)
		dockerfile.ENV("USER", username)
		dockerfile.ENV("HOME", self.home())
		dockerfile.ENV("PROJECTS", self.projects())

		dockerfile.exec_command(f"# create workspace for sudo user {username}")
		dockerfile.exec_command(f"# remove sudo password for {username} (as root)")
		dockerfile.RUN([
			f"useradd -r -m -U -G sudo -d {self.home()} -s /bin/bash -c \"Docker SGE user\" {username}",
			f"echo \"{username} ALL=(ALL:ALL) NOPASSWD: ALL\" | sudo tee /etc/sudoers.d/{username}",
			f"chown -R {username} {self.home()}",
			f"mkdir {self.projects()}",
			f"chown -R {username} {self.home()}/*"
		])

		# install user packages for projects
		self.__install_projects(dockerfile)

		# last line
		dockerfile.USER(username)
		# TODO : make entrypoint a custom bash file
		dockerfile.ENTRYPOINT("sudo /usr/sbin/sshd -D")
		dockerfile.close()
		return dockerfile.filename

	def __install_projects(self, dockerfile):
		pkg = PackageManager()
		# Install projects dependencies
		for projname, project in self._config["projects"].items():
			pkg.add([] if "requires" not in project else project["requires"])

		pkg.install(dockerfile)

		# Run eventual dockerfile commands set by user:
		if "image" in project:
			for cmd in project["image"]:
				dockerfile.exec_command(cmd)


	def __setup_projects(self):
		from urllib import parse

		def clone_repo(self, repourl:str, workspace:str) -> str:
			# clone repositories (if git in name, else copy local path (?))
			if ".git" in repo:
				repo_workspace = self._engine.join(
					workspace,
					self._engine.basename(repourl).replace(".git", "")
				)

				self._engine.bash(
					cmds = f"git clone {repourl} {repo_workspace}",
					cwd = self.projects() 
				)

				return repo_workspace
			else:
				raise RuntimeError("Can only clone git repo at the moment.")

		def setup_container_repo(self, repo_workspace:str, scmprofile:dict) -> None:
			# Retrieve url from clone repo
			repourl = self._engine.evaluate("git config --get remote.origin.url", cwd = repo_workspace)[0]
			# Get site from url to generate token line
			repourl = parse.urlsplit(repourl)
			user = scmprofile["user"]
			token = scmprofile["token"]
			mail = scmprofile["mail"] if "mail" in scmprofile else None
			ghcredentials = f"{repourl.scheme}://{user}:{token}@{repourl.netloc}"
			credentials_file = self._engine.join(".git", "." + user + "-credentials")

			# Hidden token from stdout
			self._engine.bash(
				cmds = [f"echo \"{ghcredentials}\" | tee {credentials_file}"],
				cwd = repo_workspace, silent = True
			)
			self._engine.bash(
				cmds = [
					f"git config --local user.name {user}",
					f"git config --local user.email {mail}" if mail is not None else "",
					f"git config --local credential.helper \'store --file {credentials_file}\'"
				],
				cwd = repo_workspace
			)

		assert self._engine.container is not None
		# Install projects
		for projname, project in self._config["projects"].items():
			# Get project arguments

			# Get source code manager profile
			profile_found = False
			if "scmprofile" in project:
				if project["scmprofile"] in self._config["profiles"].keys():
					scmprofile = self._config["profiles"][project["scmprofile"]]
					profile_found = True
				else:
					# TODO : call self.__del__ to delete temp folder
					raise RuntimeError("Cannot find profile " + project["scmprofile"])

			if profile_found:
				# Add project workspace to the container's bashrc
				self._engine.register_env(projname.upper(), project["workspace"])

				for repo in project["sources"]:
					repo_workspace = clone_repo(self, repo, project["workspace"])
					setup_container_repo(self,
						repo_workspace = repo_workspace,
						scmprofile = scmprofile
					)
			else:
				print(f"No profile found for project {projname}, skipping clone.")

			if "setup" in project:
				for cmd in project["setup"]:
					self._engine.bash(cmd)



	def from_image(self, image:str) -> "ContainedEnv":
		self._image = self.dockerclient.images.get(image)
		return self

	def build_image(self, regenerate = False) -> "ContainedEnv":
		image = None
		try:
			image = self.dockerclient.images.get(imagename(self.config))
		except:
			image = None

		if image is None or regenerate:
			# create the docker file
			dockerfile_path = self.__build_dockerfile()

			# Build the actual image
			self._engine.image, _ = self.dockerclient.images.build(
				path = config_dir(),
				dockerfile = dockerfile_path,
				tag = imagename(self.config),
				# Remove intermediate containers. 
				# The docker build command now defaults to --rm=true, 
				# but we have kept the old default of False to preserve backward compatibility
				rm = True,
				# Always remove intermediate containers, even after unsuccessful builds
				forcerm = True
			)

			# If everything went fine, remove docker file from file system
			if self._local.isfile(dockerfile_path): self._local.unlink(dockerfile_path)
		else:
			self._engine.image = image

		return self

	def run_container(self, regenerate = True) -> "ContainedEnv":
		port_host = "6022"
		port_incontainer = "22"
		container = None
		try:
			container = self.dockerclient.containers.get(containername(self.config))
		except:
			container = None

		# First kill the container
		if regenerate and container is not None:
			container.remove(force = True)
			container = None

		if container is None and self._engine.image is None:
			raise docker.errors.ImageNotFound
		
		if container is None:
			# Find the image name tagged for this container
			matches = [tag for tag in self.image.tags if tag == f"containedenv:{appname(self.config)}"]
			if len(matches) == 0:
				raise docker.errors.ImageNotFound
				
			self._engine.container = self.dockerclient.containers.run(
				image = matches[0],
				#image = self._image.id,
				command = "bash",
				name = containername(self.config),
				hostname = appname(self.config),
				ports = {port_incontainer : port_host},
				tty = True,
				detach = True
			)
		else:
			self._engine.container = container

		self.__setup_projects()
		
		print(f"Enter this container with \"docker exec -it -u {user(self._config)} {containername(self.config)} bash\"")
		print(f"If an ssh server is running in the container, you may call \"ssh -i id_rsa -p {port_host} {user(self._config)}@localhost\"")
		return self