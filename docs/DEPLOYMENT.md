# Verified existing website workflow

Workflow reconnaissance and local release preparation on2026-10-06.
Site: https://walter.teitelbaum.us/; repo:jewbee2000/walts_jekyll_site.
Existing local checkout:C:\Users\Walt\PycharmProjects\walts_jekyll_site, clean
on gh-pages at3cd88de609fe59d59841e642dacfb8a2189112e3.

Active source branch is gh-pages. _config.yml destination is docs; generated
docs/ and root .nojekyll are tracked. main has stale posts and is not the verified
publishing source. Here generated docs must be included after the Jekyll build.
Use a separate fresh gh-pages clone/worktree for publication; preserve site style,
navigation and post layout. Ruby3.3.7/Bundler2.6.7 installed; bundle check passed.
Fresh baseline and draft article builds passed natively. Final release preview
and actual new Pages publication are still required before M7 completion.

Verification matched local, immutable GitHub and live article
https://walter.teitelbaum.us/2026/10/04/abyssbench/ with SHA256
9b2948e2c6cc5dd33de64bc8e14ebb84a9a04180984072995f46a0b25e1cb2a5.
Actual successful dynamic Pages run:
https://github.com/jewbee2000/walts_jekyll_site/actions/runs/37248239701;
deployment6848927089 identifies gh-pages and the domain. No source .github
workflow was present; dynamic pages-build-deployment handles publishing.

Before M7 writing, refresh exact source/branch and current deployment. Build source
article/assets into tracked docs, inspect desktop/mobile/equations/downloads,
review diff/PR targeting gh-pages, then publish only after lab release gates and
concrete preview pass. Verify actual Pages deployment and live URL. User already
authorized this gated publication. Do not switch hosting providers or redesign.

M7 preparation refreshed a separate clone at
C:\Users\Walt\Documents\Codex\fluid-lab-site-release, same gh-pages revision.
GitHub Pages API actually confirms legacy source gh-pages:/docs and built status;
latest successful Pages run remains37248239701. Fresh working HTML is CRLF under
the site's Git settings; hashing the immutable Git blob matches the actual live
response at9b2948e2c6cc5dd33de64bc8e14ebb84a9a04180984072995f46a0b25e1cb2a5.
Do not mistake working newline conversion for changed deployed content.
Fresh `bundle check` and `bundle exec jekyll build --trace` actually passed,
with Jekyll reporting4.129s. Original build log is in the lab's ignored
artifacts/site-baseline-build.log. A separate draft article and19-run hosted
replay were built and inspected through the local in-app browser. Final figures,
immutable release links, full preview, PR and actual publication remain pending.
