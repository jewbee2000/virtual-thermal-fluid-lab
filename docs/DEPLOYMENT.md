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
Fresh baseline and draft article builds passed natively. The preparation record
below retains what was known before release; completed publication follows it.

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
immutable release links, full preview, PR and actual publication were pending
at that preparation checkpoint.

## Verified publication on2026-10-06

Final native Jekyll build passed in9.962s. The approximately1311-word source
article uses four release-derived figures and the existing post layout.
Desktop1265px and mobile360px previews passed; mobile equations retain keyboard
scrolling. All474 source/generated replay files and four figure pairs matched
the reviewed original bytes in the actual Git index.

[Site PR1](https://github.com/jewbee2000/walts_jekyll_site/pull/1)
merged reviewed commitbe9e3b25beee8d34147cf2eea3dea39461c1f8f7 into
gh-pages at3fe8de66f153bf8bfd25325947343f05612509d1. Both trees match.
[Pages run37456973286](https://github.com/jewbee2000/walts_jekyll_site/actions/runs/37456973286)
completed successfully; deployment6882784535 reports success at11:32:29UTC.
The API still identifies the existing legacy gh-pages:/docs source, custom
domain and enforced HTTPS. No hosting provider or site templates changed.

Actual HTTPS checks compared all242 deployed article/project files,77295064B,
directly to the reviewed generated docs. Every file matched. The article HTML
SHA256 is09d4f7d14b9d7fd1617fa7e62933b96e6f300ad6f95bc2b4f7808146c3082ecb;
the hosted replay manifest is579c4f3b3fb2407d47cd3919f66ddc6e1061b34ad4f01ac5154eb0a1f0737aa4.

The live homepage link opens the article, and its replay link opens all19 runs.
Live desktop/mobile checks found no page overflow; all four figures loaded.
The stuck-heat case retains terminal466.299590s, expectationPASS,
containmentFAILED and completionFAIL. Actual browser CSV and gzip downloads
match the packaged bytes; decompressed summary matches the original.
Screenshots, response hashes, browser observations and deployment receipts are
in `evidence/M7/publication/`. Two older reused-tab console errors preceded
publication; no new live warn/error was observed, and a fresh public article
tab reported none.

[Public releasev0.1.0](https://github.com/jewbee2000/virtual-thermal-fluid-lab/releases/tag/v0.1.0)
was published at11:30:37UTC after all four final CI jobs passed atdd8b981
([run37452839832](https://github.com/jewbee2000/virtual-thermal-fluid-lab/actions/runs/37452839832)).
The annotated tag resolves to commitdd8b9814859691c7f71019bb2bca4e4d0baef284;
all19 current uploaded asset sizes/digests match the audited originals.
Commit-addressed source content is fixed; GitHub release immutability enforcement
is not enabled. The original tag/archives are preserved rather than rebuilt to
pretend this later publication record existed before deployment.

Live [case study](https://walter.teitelbaum.us/2026/10/06/virtual-thermal-fluid-lab/)
and [replay](https://walter.teitelbaum.us/assets/projects/virtual-thermal-fluid-lab/replay/).
Parameters assumed; board NOT_EXECUTED; fixture NOT_FABRICATED;
physical validation NOT_STARTED.

## Software-focused article revision on 2026-10-06

The user requested a friendlier account of the software implementation. The
revision removes the specified authorship paragraph, adds project scope and a
link to the complete requirements table, and explains the components with an
annotated architecture diagram. Separate desktop and mobile SVGs preserve
readability. A restriction recovery example uses the existing released plot
and retained scenario records. Thermal equations and the original results and
figures remain. The revised article has 1,361 words and six figures.

The native `bundle exec jekyll build --trace` passed in 7.467 s. Read-only
architecture and scenario reviews accepted the source-grounded descriptions.
Actual desktop (1,265 px) and mobile (360 px) browser checks found no page
overflow; the requirements link was activated, equations scrolled with the
keyboard, and all figures loaded. A fresh live browser console had no errors.

[Site PR 2](https://github.com/jewbee2000/walts_jekyll_site/pull/2) merged reviewed
source `64d0f1a260d613aaae57b1a689bb965925aa7b60` into gh-pages at
`ca80f0e55b0f51884f15a5d350c9ff5395390901`; their Git trees match.
[Pages run 37484616287](https://github.com/jewbee2000/walts_jekyll_site/actions/runs/37484616287)
completed successfully, and deployment `6887629992` reports success.
Thirteen updated or referenced HTTPS files matched the reviewed immutable Git
blobs. The current article HTML SHA256 is
`bf6a124285db85e031ec53a9f082ce38eadfada05c08bb8cf0be1e94b4858878`;
the earlier publication hash above describes the original article version.

Receipts and an actual screenshot of the published diagram are in
`evidence/website/article-software-update-20261006/`. All 237 replay files in
each source/generated tree are unchanged. This article-only update changes no
simulation, firmware, acceptance threshold, dependency, or v0.1.0 release
artifact. No new simulation or hardware measurement was performed. Board
execution remains NOT_EXECUTED and physical validation remains NOT_STARTED.
