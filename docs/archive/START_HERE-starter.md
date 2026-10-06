# First session and computer setup

## Recommended environment

Use your existing Linux/Python workflow. Ubuntu 24.04 or Windows 11 with WSL2 Ubuntu is a practical default for this project. A normal laptop is enough; my planning allowance is four CPU cores, 16 GB RAM and 5 GB free disk. There is no GPU or cloud simulation requirement. Native Windows can run the Python project too, but the commands below assume Bash.

If using Windows, install WSL from an administrator PowerShell terminal:

```powershell
wsl --install -d Ubuntu-24.04
wsl --list --verbose
```

Restart if requested, launch Ubuntu, and create its Linux user. If that distro name is unavailable, inspect `wsl --list --online` and choose an available Ubuntu distribution. Work under `~/projects`, not `/mnt/c`, for Linux tools. Use VS Code's WSL extension if you want an editor. Microsoft documents WSL installation [S14] and filesystem interoperability [S15].

In Ubuntu:

```bash
sudo apt update
sudo apt install -y git curl unzip
mkdir -p ~/projects
cd ~/projects
```

Download and extract `virtual-fluid-lab-starter.zip` into this directory. In WSL, a Windows download can be extracted with `unzip /mnt/c/Users/YOUR_WINDOWS_USER/Downloads/virtual-fluid-lab-starter.zip`. It creates `virtual-fluid-lab/`.

Install uv using its official installer [S10]. Download before executing so you can inspect it:

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/fluidlab-uv-install.sh
less /tmp/fluidlab-uv-install.sh
sh /tmp/fluidlab-uv-install.sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
cd ~/projects/virtual-fluid-lab
uv python install 3.12
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run fluidlab scenarios/nominal.json --out artifacts/nominal --plot
uv run python scripts/run_suite.py
```

Open `artifacts/nominal/plot.png`. Compare its true and measured levels. Inspect `summary.json`, `telemetry.csv`, and `manifest.json`. A `PASS` on `pump_stuck_on` means the test successfully exposed the expected hazard; the run reaches the full-tank domain boundary.

## Install and launch Codex

Use the current official installer and your existing ChatGPT sign-in [S11]. Installing the Windows app does not necessarily install the CLI inside Ubuntu; keep the executable and project in the same environment. This matters given your earlier `codex not recognized` error.

```bash
curl -fsSL https://chatgpt.com/codex/install.sh -o /tmp/fluidlab-codex-install.sh
less /tmp/fluidlab-codex-install.sh
sh /tmp/fluidlab-codex-install.sh
```

Open a new Ubuntu terminal if the command is not found. Then:

```bash
command -v codex
codex --version
cd ~/projects/virtual-fluid-lab
codex
```

Sign in when prompted. Use the model available in your account; the included agent definitions inherit it. Keep ordinary workspace permissions. Nothing here needs unrestricted access, remote control, a vendor DAQ account, or a separate Agents SDK API key. Account limits and installed client capabilities may vary.

Before delegation, initialize Git and record the baseline:

```bash
git init -b main
# If Git requests identity, configure your own name/email locally.
git add .
git commit -m "Add verified educational fluid SIL starter"
```

Read `prompts/00-kickoff.md` and paste it into Codex. The project config caps spawned agent threads at three, excluding the coordinator. Current documentation describes standalone custom agents in `.codex/agents/*.toml` [S12]. Use `/agent` to inspect active threads where supported. If your installed client rejects these settings, remove or temporarily rename `.codex/config.toml` and use the same Markdown prompts in separate chats/worktrees. Do not invent legacy configuration keys to silence an error.

## Spend the first 90 minutes this way

1. **0–20 minutes:** install tools, run tests, open the nominal plot.
2. **20–40 minutes:** read `MODEL.md`; hand-calculate the drain flow at 0.5 m and the time to add 1 L at 6 L/min. Check those against a short simulation.
3. **40–60 minutes:** run the bias and stuck-pump scenarios with `--plot`; explain why the level continues rising briefly after the stop command.
4. **60–90 minutes:** launch the kickoff prompt. Work only on ticket T01: review assumptions and freeze interfaces. Read the agents' disagreements before accepting their conclusions.

Only the account sign-in and software installation require your local involvement. GitHub is optional until you choose to publish the repository; this package does not create an account, repository, or public deployment.
