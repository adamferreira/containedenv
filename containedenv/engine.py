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
		self._engine = DockerEngine()
		# public
		self.dockerclient = docker.from_env()

	def __build_dockerfile(self):
		# Create the dockerfile
		dockerfile = UbuntuDockerFile(
			self._local.join(config_dir(), f"Dockerfile.{appname(self.config)}")
		)
		# install packages
		dockerfile.install("sudo")
		self.__install(dockerfile)

		# create the user workspace
		username = user(self._config)
		dockerfile.exec_command(f"# create workspace for sudo user {username}")
		# new user belongs to sudo group
		dockerfile.RUN(f"useradd -r -m -U -G sudo -d /home/{username} -s /bin/bash -c \"Docker SGE user\" {username}")
		# remove sudo password for {username} (as root)
		dockerfile.exec_command(f"# remove sudo password for {username} (as root)")
		dockerfile.RUN(f"echo \"{username} ALL=(ALL:ALL) NOPASSWD: ALL\" | sudo tee /etc/sudoers.d/{username}")
		#dockerfile.RUN(f"usermod -aG sudo {username}")
		dockerfile.RUN(f"chown -R {username} /home/{username}")
		dockerfile.RUN(f"mkdir /home/{username}/projects")
		dockerfile.RUN(f"chown -R {username} /home/{username}/*")

		# last line
		dockerfile.ENTRYPOINT("/bin/bash")
		# destructor of dockerfile will close the file
		return dockerfile.script.name

	def __install(self, dockerfile):
		for confname, conf in self._config["install"].items():
			dockerfile.exec_command(f"# packages for configuration {confname}")
			dockerfile.install(conf["packages"])



	def from_image(self, image:str) -> "ContainedEnv":
		self._image = self.dockerclient.images.get(image)
		return self

	def build_image(self, regenerate = True) -> "ContainedEnv":
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

	def run_container(self, regenerate = False) -> "ContainedEnv":
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

		self.container.logs()
		print(f"Enter this container with \"docker exec -it -u {user(self._config)} {containername(self.config)} bash\"")
		#self.dockerclient.images.remove(matches[0], force = True)
		return self


	def setup_github(self) -> "ContainedEnv":
		def get_github_credentials(user:str, token:str) -> str:
			# git config --global credential.helper 'store --file ~/.my-credentials'
			return f"https://{user}:{token}@github.com"

		assert self.container is not None
		user = "testuser"
		token = "testoken"
		credentials_file = "/home/.git-credentials"
		credentials_line = get_github_credentials(user, token)
		
		# Create credentials file
		self._engine.exec_command(f"echo \"{credentials_line}\" > {credentials_file}")
		# Store credentials into git configuration
		self._engine.exec_command(f"git config --global credential.helper \'store --file {credentials_file}\'")