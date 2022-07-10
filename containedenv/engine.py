from asyncio import streams
from typing import Generator
import docker
from dockerfile import UbuntuDockerFile
from config import config_dir
from pyrc.system import FileSystem, LocalFileSystem, FileSystemCommand, OSTYPE
import pyrc.event as pyevent


class DockerEngine(FileSystemCommand):
	"""
	DockerEngine is will submit evey generated command (FileSystemCommand)
	to a docker client
	"""
	def __init__(self, image = None, container = None) -> None:
		FileSystemCommand.__init__(self)
		# Only works with linux style commands for now
		self.ostype = OSTYPE.LINUX
		self.image = image
		self.container = container

	def exec_command(self, cmd:str, cwd:str = "", environment:dict = None, event = None):
		assert self.container is not None

		exit_code, outputs = self.container.exec_run(
			cmd = cmd,
			workdir = cwd,
			environment = environment,
			stdout = True, stderr = True, stdin = False,
			demux = False, # Return stdout and stderr separately,
			stream = True
		)
		srdoutflux = outputs # Output is a Generator type (isinstance(outputs, Generator) == 1)
		event = pyevent.CommandPrettyPrintEvent(self, print_input=True, print_errors=True) if event is None else event
		event.begin(cmd, cwd, stdin = None, stderr = None, stdout = srdoutflux)
		return event.end() 

	#@overrides Necessary for FileSystem.__init__(self) as we overrides ostype
	def platform(self) -> 'dict[str:str]':
		return {
			"system" : FileSystem.os_to_str(FileSystem.ostype),
			"platform" : "unknown"
		}

		

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
		self._local = LocalFileSystem()
		self._workspace = config_dir()
		self._config = config
		self.dockerclient = docker.from_env()
		self._engine = DockerEngine()

	def from_image(self, image:str) -> "ContainedEnv":
		self._image = self.dockerclient.images.get(image)
		return self

	def build_image(self) -> "ContainedEnv":
		appname = "testapp"
		imagename = f"containedenv:{appname}"
		dockerfilepath = self._local.join(self._workspace, f"Dockerfile.{appname}")

		# TODO check if image already exists (?)

		# Create docker file on file system
		dockerfile = UbuntuDockerFile(dockerfilepath)
		dockerfile.install("git")
		# Trigger write (TODO do better)
		del dockerfile

		# Build the actual image
		self._engine.image, _ = self.dockerclient.images.build(
			path = self._workspace,
			dockerfile = dockerfilepath,
			tag = imagename,
			# Remove intermediate containers. 
			# The docker build command now defaults to --rm=true, 
			# but we have kept the old default of False to preserve backward compatibility
			rm = True,
			# Always remove intermediate containers, even after unsuccessful builds
			forcerm = True
		)

		# If everything went fine, remove docker file from file system
		if self._local.isfile(dockerfilepath): self._local.unlink(dockerfilepath)

		return self

	def run_container(self) -> "ContainedEnv":
		if self._engine.image is None:
			raise docker.errors.ImageNotFound

		appname = "testapp"
		containername = f"{appname}_cnt"
		
		# Find the image name tagged for this container
		matches = [tag for tag in self.image.tags if tag == f"containedenv:{appname}"]
		if len(matches) == 0:
			raise docker.errors.ImageNotFound

		self._engine.container = self.dockerclient.containers.run(
			image = matches[0],
			#image = self._image.id,
			command = "bash",
			name = containername,
			hostname = appname,
			tty = True,
			detach = True
		)

		self.container.logs()
		print(f"Enter this container with \"docker exec -it {containername} bash\"")
		#self.dockerclient.images.remove(matches[0], force = True)
		return self


	def setup_github(self) -> "ContainedEnv":
		def get_github_credentials(user:str, token:str) -> str:
			# git config --global credential.helper 'store --file ~/.my-credentials'
			return f"https://{user}:{token}@github.com"

		assert self.container is not None
		user = "testuser"
		token = "testoken"
		credentials_file = "~/.git-credentials"
		credentials_line = get_github_credentials(user, token)
		
		# Create credentials file
		self._engine.exec_command(f"echo \"{credentials_line}\" >> {credentials_file}")
		# Store credentials into git configuration
		self._engine.exec_command(f"git config --global credential.helper \'store --file {credentials_file}\'")