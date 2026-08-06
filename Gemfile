source "https://rubygems.org"

gem "jekyll", "~> 4.3"
gem "webrick", "~> 1.8"

# Formerly stdlib, unbundled from Ruby 3.4+ but still required by Jekyll's
# dependency chain.
gem "csv"
gem "base64"
gem "bigdecimal"
gem "logger"

group :jekyll_plugins do
  gem "jekyll-seo-tag"
  gem "jekyll-sitemap"
  gem "jekyll-feed"
end

group :test do
  gem "html-proofer", "~> 5.0"
end
