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
		return self._local

	@property
	def args(self):
		return self._config.args

	def __init__(self, config:Config) -> None:
		# protected
		self._local = LocalFileSystem()
		self._config = config
		self._engine = DockerEngine(user = self.config.app.user)
		self._dockerclient = docker.from_env()

		print(self.config)

	def home(self) -> str:
		return f"/home/{self.config.app.user}"

	def projects(self) -> str:
		return f"{self.home()}/projects"

	def __build_dockerfile(self):
		# Create the dockerfile
		dockerfile = UbuntuDockerFile(
			self._local.join(config_dir(), f"Dockerfile.{self.config.appname()}")
		)
		# install packages
		dockerfile.install(["sudo", "wget", "curl"])

		# create the user workspace
		username = self.config.app.user
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
		for projname in self.args.projects:
			if projname not in  self._config["projects"].keys():
				print(f"Project {projname} not found, ignoring.")
				continue
			project = self._config["projects"][projname]
			pkg.add([] if "requires" not in project else project["requires"])

		pkg.install(dockerfile)
	
		for projname in self.args.projects:
			if projname not in  self._config["projects"].keys():
				print(f"Project {projname} not found, ignoring.")
				continue
			project = self._config["projects"][projname]
			# Run eventual dockerfile commands set by user:
			if "image" in project:
				for cmd in project["image"]:
					# TODO evaluate path
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
			mail = scmprofile["mail"] if "mail" in scmprofile else None

			# get user token
			token = scmprofile["token"] if "token" in scmprofile else self.args.ghtoken
			if token is not None:
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
					f"git config --local credential.helper \'store --file {credentials_file}\'" if token is not None else "",
				],
				cwd = repo_workspace
			)

		assert self._engine.container is not None

		# To correct : fatal: unable to access <repo>: server certificate verification failed. CAfile: none CRLfile: none
		# Either put export GIT_SSL_NO_VERIFY=1 in image
		# Or config git in container : git config --global http.sslverify false
		self._engine.bash("git config --global http.sslverify false")

		# Install projects
		for projname in self.args.projects:
			if projname not in self._config["projects"].keys():
				print(f"Project {projname} not found, ignoring.")
				continue
			
			project = self._config["projects"][projname]
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
					#self._engine.evaluate_path(cmd)
					self._engine.bash(cmd)



	def from_image(self, image:str) -> "ContainedEnv":
		self._image = self._dockerclient.images.get(image)
		return self

	def build_image(self) -> "ContainedEnv":
		image = None
		try:
			image = self._dockerclient.images.get(self.config.imagename())
			# If rebuild, force destroy image and remove linked container
			if self.args.rebuild:
				try:
					container = self._dockerclient.containers.get(self.config.containername())
					container.remove(force = True)
					container = None
				except:
					container = None

				self._dockerclient.images.remove(
					image = image.id, force = True
				)
				image = None
		except Exception as e:
			print(e)
			image = None

		if image is None:
			# create the docker file
			dockerfile_path = self.__build_dockerfile()

			# Build the actual image
			self._engine.image, _ = self._dockerclient.images.build(
				path = config_dir(),
				dockerfile = dockerfile_path,
				tag = self.config.imagename(),
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

	def run_container(self) -> "ContainedEnv":
		container = None
		try:
			container = self._dockerclient.containers.get(self.config.containername())
		except:
			container = None

		# First kill the container
		if self.args.rebuild and container is not None:
			container.remove(force = True)
			container = None

		if container is None and self._engine.image is None:
			raise docker.errors.ImageNotFound
		
		if container is None:
			# Find the image name tagged for this container
			matches = [tag for tag in self.image.tags if tag == self.config.imagename()]
			if len(matches) == 0:
				raise docker.errors.ImageNotFound
				
			self._engine.container = self._dockerclient.containers.run(
				image = matches[0],
				#image = self._image.id,
				command = "bash",
				name = self.config.containername(),
				hostname = self.config.appname(),
				ports = {p.split(":")[0] : p.split(":")[1] for p in self.args.ports},
				tty = True,
				detach = True
			)
		else:
			self._engine.container = container

		self.__setup_projects()
		
		print(f"Enter this container with \"docker exec -it -u {self.config.user()} {self.config.containername()} bash\"")
		print(f"If an ssh server is running in the container, you may call \"ssh -i id_rsa -p <port> {self.config.user()}@localhost\"")
		return self