# ...moved from root, see previous content...

class Spiderfoot < Formula
  include Language::Python::Virtualenv

  desc "Open Source Intelligence Automation Tool"
  homepage "https://github.com/poppopjmp/spiderfoot"
  url "https://github.com/poppopjmp/spiderfoot/archive/refs/tags/v5.2.7.tar.gz"
  sha256 "SKIP" # Replace with actual sha256sum for the release tarball
  license "MIT"

  depends_on "python@3.9"
  depends_on "libpq" # For psycopg2-binary

  def install
    virtualenv_install_with_resources

    # Install main scripts as CLI entry points
    bin.install "sf.py" => "spiderfoot"
    bin.install "sfcli.py" => "spiderfoot-cli"
    bin.install "sfapi.py" => "spiderfoot-api"

    # Install all modules, correlations, and spiderfoot code/data
    (libexec/"modules").install Dir["modules/*"]
    (libexec/"correlations").install Dir["correlations/*"]
    (libexec/"spiderfoot").install Dir["spiderfoot/*"]

    # Install all sf* and sflib* files from root
    root_files = Dir["sf*.py", "sflib.py", "sfscan.py", "sfwebui.py", "sfworkflow.py"]
    (libexec/"root").install root_files

    # Optionally install man pages if present
    man1.install "packaging/spiderfoot.1" if File.exist?("packaging/spiderfoot.1")
    man1.install "packaging/spiderfoot-cli.1" if File.exist?("packaging/spiderfoot-cli.1")
    man1.install "packaging/spiderfoot-api.1" if File.exist?("packaging/spiderfoot-api.1")
  end

  test do
    system "#{bin}/spiderfoot", "--help"
    system "#{bin}/spiderfoot-cli", "--help"
    system "#{bin}/spiderfoot-api", "--help"
  end
end
