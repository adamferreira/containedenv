from distutils.command.config import config
import docker
from pyrc.system import LocalFileSystem
from pyrc.docker import DockerEngine
from containedenv.dockerfile import UbuntuDockerFile
from containedenv.packages import PackageManager, PackageManager2
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
			self.local.join(config_dir(), f"Dockerfile.{self.config.appname()}"),
			self.config.app.imgfrom,
			"root"
		)

		# install utilitary packages
		dockerfile.install(["sudo", "wget", "curl"])

		# create the user workspace
		username = self.config.app.user
		dockerfile.ENV("USER", username)
		dockerfile.ENV("HOME", self.home())
		dockerfile.ENV("PROJECTS", self.projects())

		dockerfile.writeline(f"# create workspace for sudo user {username}")
		dockerfile.writeline(f"# remove sudo password for {username} (as root)")
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
		#dockerfile.ENTRYPOINT("sudo /usr/sbin/sshd -D")
		dockerfile.close()
		return dockerfile.filename

	def __install_projects(self, dockerfile):
		# Create Package manager
		pkg = PackageManager2(self.config, dockerfile)
		# Install project dependencies
		[pkg.install_project_packages(p) for p in self.config.projects]
		# Run docker commands for projects
		for project in self.config.projects:
			if project.name not in self.args.projects:
				continue
			dockerfile.writelines(project.image)


	def __setup_projects(self):
		from urllib import parse

		def __clone_repo(self, repourl:str, workspace:str) -> str:
			# clone repositories (if git in name, else copy local path (?))
			if ".git" in repourl:
				repo_workspace = self._engine.join(
					workspace,
					self._engine.basename(repourl).replace(".git", "")
				)

				self._engine.bash(
					cmds = f"git clone {repourl} {repo_workspace}",
					cwd = workspace
				)

				return repo_workspace
			else:
				raise RuntimeError("Can only clone git repo at the moment.")

		def __configure_repository(self, repo_workspace:str, ghprofile:GithubProfile) -> None:
			if ghprofile is None: return
			# Retrieve url from cloned repo
			repourl = self._engine.evaluate("git config --get remote.origin.url", cwd = repo_workspace)[0]
			# Get site from url to generate token line
			repourl = parse.urlsplit(repourl)
			user = ghprofile.user
			mail = ghprofile.mail
			token = ghprofile.token if ghprofile.token is not None else self.args.ghtoken

			# Add token as a credential
			if token is not None:
				ghcredentials = f"{repourl.scheme}://{user}:{token}@{repourl.netloc}"
				credentials_file = self._engine.join(".git", "." + user + "-credentials")
				# Hidden token from stdout
				self._engine.bash(
					cmds = [f"echo \"{ghcredentials}\" | tee {credentials_file}"],
					cwd = repo_workspace, silent = True
				)

			# Configure repository user and mail
			self._engine.bash(
				cmds = [
					f"git config --local user.name {user}",
					f"git config --local user.email {mail}" if mail is not None else "",
					f"git config --local credential.helper \'store --file {credentials_file}\'" if token is not None else "",
				],
				cwd = repo_workspace
			)
			
		def __setup_project(self, project:Project):
			# Step one, clone repositories of the projects
			for repourl in project.sources:
				repo_workspace = __clone_repo(self, repourl, project.workspace)
				__configure_repository(self, repo_workspace, self.config.github_profile)



		assert self._engine.container is not None

		# To correct : fatal: unable to access <repo>: server certificate verification failed. CAfile: none CRLfile: none
		# Either put export GIT_SSL_NO_VERIFY=1 in image
		# Or config git in container : git config --global http.sslverify false
		self._engine.bash("git config --global http.sslverify false")

		# Install projects
		for project in self.config.projects:
			if project.name not in self.args.projects:
				print(f"Project {project.name } not found, ignoring.")
				continue

			# Add project workspace to the container's bashrc
			self._engine.register_env(project.name.upper(), project.workspace)
			# Clone and configure project's repositories
			__setup_project(self, project)
			# Call custom commands of the project in the container (if any)
			[self._engine.bash(cmd, project.workspace) for cmd in project.container]



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
			# No existing image found, we thus create a new one
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