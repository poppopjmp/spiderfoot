# ...moved from root, see previous content...

class Spiderfoot < Formula
  include Language::Python::Virtualenv

  desc "Open Source Intelligence Automation Tool"
  homepage "https://github.com/poppopjmp/spiderfoot"
  url "https://github.com/poppopjmp/spiderfoot/archive/refs/tags/v6.0.0.tar.gz"
  sha256 "SKIP" # Replace with actual sha256sum for the release tarball
  license "MIT"

  depends_on "python@3.10"
  depends_on "libpq" # For psycopg2-binary

  def install
    virtualenv_install_with_resources

    # Install main script as CLI entry point
    bin.install "sfapi.py" => "spiderfoot-api"

    # Install all modules, correlations, and spiderfoot code/data
    (libexec/"modules").install Dir["modules/*"]
    (libexec/"correlations").install Dir["correlations/*"]
    (libexec/"spiderfoot").install Dir["spiderfoot/*"]

    # Install root entry point
    root_files = Dir["sfapi.py"]
    (libexec/"root").install root_files

    # Optionally install man pages if present
    man1.install "packaging/spiderfoot-api.1" if File.exist?("packaging/spiderfoot-api.1")
  end

  test do
    system "#{bin}/spiderfoot-api", "--help"
  end
end
