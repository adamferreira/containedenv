from pyrc.system import LocalFileSystem
from containedenv.config import config_dir, Config, Project, Package
from containedenv.dockerfile import DockerFile


class PackageManager2(object):
	def __init__(self, config:Config, dockerfile:DockerFile) -> None:
		# Packages dictionnary for easier handling
		self.packages:dict = {
			p.name : p for p in config.packages
		}
		# Dockerfile
		self.dockerfile:DockerFile = dockerfile
		# Installed packages (names)
		self.installed:set = set()

	def install_package(self, pkg:str) -> None:
		# Skip if package is note found in packages list
		if not pkg in self.packages: return
		# Skip if package is already installed
		if pkg in self.installed: return

		_pkg:Package = self.packages[pkg]
		# Step one, install apt packages in any
		self.dockerfile.install(_pkg.apt_packages)
		# Step two, append a given docker file if any
		if _pkg.dockerfile is not None:
			_pkg.dockerfile.append_dockerfile(_pkg.dockerfile)
		# Step three, executing given custom dockerfile commands
		self.dockerfile.writlelines(_pkg.image)
		# Step four, mark package as already installed
		self.installed.add(pkg)

	def install_project_packages(self, project:Project) -> None:
		[self.install_package(pkg) for pkg in project.requires]



class PackageManager(object):
	def __init__(self) -> None:
		self.special_packages = {
			"julia" : [],
			"python" : ["python3", "python3-distutils"],
			"homebrew" : []
		}
		self.installed = set()
		self.toinstall = set()

	def __install_python(self, dockerfile):
		PYTHON_GET_PIP_URL = "https://github.com/pypa/get-pip/raw/6ce3639da143c5d79b44f94b04080abf2531fd6e/public/get-pip.py"
		PYTHON_GET_PIP_SHA256 = "ba3ab8267d91fd41c58dbce08f76db99f747f716d85ce1865813842bb035524d"
		pip_lines = [
			f"wget -O get-pip.py {PYTHON_GET_PIP_URL}",
			f"echo \"{PYTHON_GET_PIP_SHA256} *get-pip.py\" | sha256sum -c -",
			f"python3 get-pip.py --no-cache-dir --no-compile",
			f"rm -f get-pip.py",
			# alias python to python3
			f"echo \"alias python=python3\" >> $HOME/.bashrc",
			f"pip --version"
		]
		#pip_lines.insert(0, f"DEBIAN_FRONTEND=noninteractive apt-get install -y python3-distutils")

		dockerfile.exec_command(f"# setting up pip")
		dockerfile.RUN(pip_lines)

	def __install_julia(self, dockerfile):
		juliafile = LocalFileSystem().join(config_dir(), "julia.dockerfile")
		dockerfile.append_dockerfile(juliafile)
		dockerfile.exec_command(f"# installing julia")
		dockerfile.RUN(f"sudo bash -ci \"$(curl -fsSL https://raw.githubusercontent.com/abelsiqueira/jill/main/jill.sh)\" --yes --no-confirm")

	def __install_homebrew(self, dockerfile):
		# Download homebrew and Change rights
		dockerfile.exec_command(f"# installing homebrew")
		dockerfile.RUN([
			"sudo NONINTERACTIVE=1 /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"",
			"chown -R $USER /home/linuxbrew/"
		])
		# Add brew to PATH
		dockerfile.ENV("PATH", "/home/linuxbrew/.linuxbrew/bin:$PATH")
		


	def isinstalled(self, pkg:str) -> bool:
		return pkg in self.installed

	def add(self, pkgs:'list[str]'):
		for pkg in pkgs:
			if not self.isinstalled(pkg):
				self.toinstall.add(pkg)

	def __install_special_pkg(self, pkg:str, dockerfile):
		if self.isinstalled(pkg):
			#print(f"Package {pkg} already installed, skipping.")
			return

		if pkg == "python":
			self.__install_python(dockerfile)

		elif pkg == "julia":
			self.__install_julia(dockerfile)

		elif pkg == "homebrew":
			self.__install_homebrew(dockerfile)



		self.installed.add(pkg)
		self.toinstall.discard(pkg)


	def install(self, dockerfile):
		pkgs = set()
		spkgs = set()
		# Separate normal and special packages
		for pkg in self.toinstall:
			if pkg in self.special_packages.keys():
				spkgs.add(pkg)
			else:
				pkgs.add(pkg)

		# Get special package dependancies
		for pkg in spkgs:
			for dependency in self.special_packages[pkg]:
				pkgs.add(dependency)

		# Install all normal packages in one go
		dockerfile.exec_command(f"# install all projects packages")
		dockerfile.install(list(pkgs))
		[self.toinstall.discard(pkg) for pkg in pkgs]
		[self.installed.add(pkg) for pkg in pkgs]
		# Install special packages
		for pkg in spkgs:
			self.__install_special_pkg(pkg, dockerfile)



		
	