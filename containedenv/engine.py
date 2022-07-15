import docker
from pyrc.system import LocalFileSystem
from pyrc.docker import DockerEngine
from containedenv.dockerfile import UbuntuDockerFile
from containedenv.config import *

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

		# install user packages
		self.__install_packages(dockerfile)

		# last line
		dockerfile.USER(username)
		dockerfile.CMD("/bin/bash")
		dockerfile.close()
		return dockerfile.filename

	def __install_packages(self, dockerfile):
		packages = []
		exclusion_list = ["julia"]
		for confname, conf in self._config["install"].items():
			packages.extend(conf["packages"])

		packages = set(packages)
		python3_found = sum([ 1 if "python3" in p else 0 for p in packages]) > 0
		distutils_found = sum([ 1 if "python3-distutils" in p else 0 for p in packages]) > 0
		julia_found = sum([ 1 if "julia" in p else 0 for p in packages]) > 0
		dockerfile.install([p for p in packages if p not in exclusion_list])

		# If python is in the packages list, intall pip
		# source : https://github.com/docker-library/python/blob/88bd0509d8c7cb3923c0b7fd5d3c05732a2e201c/3.11-rc/bullseye/Dockerfile
		if python3_found:
			PYTHON_GET_PIP_URL = "https://github.com/pypa/get-pip/raw/6ce3639da143c5d79b44f94b04080abf2531fd6e/public/get-pip.py"
			PYTHON_GET_PIP_SHA256 = "ba3ab8267d91fd41c58dbce08f76db99f747f716d85ce1865813842bb035524d"
			pip_lines = [
				f"wget -O get-pip.py {PYTHON_GET_PIP_URL}",
				f"echo \"{PYTHON_GET_PIP_SHA256} *get-pip.py\" | sha256sum -c -",
				f"python3 get-pip.py --no-cache-dir --no-compile",
				f"rm -f get-pip.py",
				f"pip --version"
			]
			if not distutils_found:
				pip_lines.insert(0, f"DEBIAN_FRONTEND=noninteractive apt-get install -y python3-distutils")

			dockerfile.exec_command(f"# setting up pip")
			dockerfile.RUN(pip_lines)

		# Julia setup
		if julia_found:
			if False:
				juliafile = self._local.join(config_dir(), "julia.dockerfile")
				dockerfile.append_dockerfile(juliafile)
			dockerfile.exec_command(f"# installing julia")
			dockerfile.RUN(f"sudo bash -ci \"$(curl -fsSL https://raw.githubusercontent.com/abelsiqueira/jill/main/jill.sh)\" --yes --no-confirm")


	def __install_projects(self):
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
					f"git config --local credential.helper \'store --file {credentials_file}\'"
				],
				cwd = repo_workspace
			)

		assert self._engine.container is not None
		# Install projects
		for projname, project in self._config["projects"].items():
			# Get source code manager profile
			if project["scmprofile"] in self._config["profiles"].keys():
				scmprofile = self._config["profiles"][project["scmprofile"]]
			else:
				# TODO : call self.__del__ to delete temp folder
				raise RuntimeError("Cannot find profile " + project["scmprofile"])

			
			# Add project workspace to the container's bashrc
			self._engine.register_env(projname.upper(), project["workspace"])

			for repo in project["sources"]:
				repo_workspace = clone_repo(self, repo, project["workspace"])
				setup_container_repo(self,
					repo_workspace = repo_workspace,
					scmprofile = scmprofile
				)

			if "post_clone_cmds" in project:
				for cmd in project["post_clone_cmds"]:
					self._engine.bash(cmd)
					

		# TODO : have one git credential by profiles
		def __install_config(self):
			return NotImplemented



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
				tty = True,
				detach = True
			)
		else:
			self._engine.container = container

		self.__install_projects()
		
		print(f"Enter this container with \"docker exec -it -u {user(self._config)} {containername(self.config)} bash\"")
		return self