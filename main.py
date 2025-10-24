import minecraft_launcher_lib
import subprocess
import os
import threading
import webview
import json
import shutil
import requests
from datetime import datetime

# Path to HeartfallLauncher Minecraft directory
minecraft_directory = os.path.join(
    os.path.expanduser("~"),
    "AppData", "Local", "EclipseLauncher"
)

config_file = os.path.join(minecraft_directory, "launcher_config.json")
os.makedirs(minecraft_directory, exist_ok=True)


class MinecraftLauncher:
    def __init__(self):
        self.window = None
        self.max_value = 0
        self.current_progress = 0
        self.config = self.load_config()

    def load_config(self):
        """Load launcher configuration"""
        default_config = {
            "last_username": "",
            "ram_allocation": 2,
            "theme": "purple",
            "dark_mode": True,
            "tutorial_shown": False,
            "launch_history": []
        }

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return {**default_config, **json.load(f)}
            except:
                return default_config
        return default_config

    def save_config(self):
        """Save launcher configuration"""
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_config(self):
        """Return config to JavaScript"""
        return self.config

    def update_username(self, username):
        """Save username"""
        self.config['last_username'] = username
        self.save_config()

    def update_ram(self, ram):
        """Save RAM allocation"""
        self.config['ram_allocation'] = ram
        self.save_config()

    def update_theme(self, theme):
        """Save theme preference"""
        self.config['theme'] = theme
        self.save_config()

    def update_dark_mode(self, dark_mode):
        """Save dark mode preference"""
        self.config['dark_mode'] = dark_mode
        self.save_config()

    def get_uuid(self, username):
        """Get Minecraft UUID from username"""
        try:
            r = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{username}")
            if r.status_code == 200:
                return r.json()["id"]
            else:
                return None
        except:
            return None

    def mark_tutorial_complete(self):
        """Mark tutorial as shown"""
        self.config['tutorial_shown'] = True
        self.save_config()

    def reset_launcher_data(self):
        """Reset all launcher configuration data"""
        try:
            if os.path.exists(config_file):
                os.remove(config_file)
            self.config = self.load_config()
            return {"success": True, "message": "Launcher data reset successfully!"}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def delete_minecraft_instances(self):
        """Delete all Minecraft instances"""
        try:
            versions_dir = os.path.join(minecraft_directory, "versions")
            if os.path.exists(versions_dir):
                shutil.rmtree(versions_dir)

            libraries_dir = os.path.join(minecraft_directory, "libraries")
            assets_dir = os.path.join(minecraft_directory, "assets")

            if os.path.exists(libraries_dir):
                shutil.rmtree(libraries_dir)
            if os.path.exists(assets_dir):
                shutil.rmtree(assets_dir)

            return {"success": True, "message": "All Minecraft instances deleted successfully!"}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def add_launch_history(self, version, username):
        """Add entry to launch history"""
        history_entry = {
            "version": version,
            "username": username,
            "timestamp": datetime.now().isoformat()
        }

        self.config['launch_history'].insert(0, history_entry)
        self.config['launch_history'] = self.config['launch_history'][:10]
        self.save_config()

        if self.window:
            self.window.evaluate_js(f'loadHistory({json.dumps(self.config["launch_history"])})')

    def get_versions(self):
        """Get available Minecraft versions"""
        av_versions = minecraft_launcher_lib.utils.get_available_versions(minecraft_directory)

        versions = {
            "release": [v['id'] for v in av_versions if v['type'] == 'release'],
            "snapshot": [v['id'] for v in av_versions if v['type'] == 'snapshot'],
            "old_beta": [v['id'] for v in av_versions if v['type'] == 'old_beta'],
            "old_alpha": [v['id'] for v in av_versions if v['type'] == 'old_alpha']
        }

        return versions

    def set_status(self, status):
        """Update status in GUI"""
        if self.window:
            self.window.evaluate_js(f'updateStatus("{status}")')

    def set_progress(self, progress):
        """Update progress in GUI"""
        self.current_progress = progress
        if self.max_value > 0:
            percentage = int((self.current_progress / self.max_value) * 100)
            if self.window:
                self.window.evaluate_js(f'updateProgress({percentage}, {self.current_progress}, {self.max_value})')

    def set_max(self, new_max):
        """Set maximum progress value"""
        self.max_value = new_max

    def install_and_launch(self, version, username, ram):
        """Install and launch Minecraft version"""
        try:
            self.set_status(f"Installing Minecraft {version}...")

            callback = {
                "setStatus": self.set_status,
                "setProgress": self.set_progress,
                "setMax": self.set_max
            }

            minecraft_launcher_lib.install.install_minecraft_version(
                version,
                minecraft_directory,
                callback=callback
            )

            self.set_status(f"Minecraft {version} installed successfully!")

            options = {
                "username": username,
                "uuid": "",
                "token": "",
                "jvmArguments": [f"-Xmx{ram}G", f"-Xms{max(1, ram // 2)}G"]
            }

            self.set_status(f"Launching Minecraft {version}...")
            minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
                version,
                minecraft_directory,
                options
            )

            subprocess.Popen(minecraft_command)

            self.set_status("Minecraft launched successfully!")

            self.add_launch_history(version, username)

        except Exception as e:
            self.set_status(f"Error: {str(e)}")

    def launch(self, data):
        """Launch handler called from JavaScript"""
        version = data.get('version')
        username = data.get('username')
        ram = data.get('ram', 2)

        if not version or not username:
            self.set_status("Please select a version and enter a username")
            return

        self.update_username(username)
        self.update_ram(ram)

        thread = threading.Thread(target=self.install_and_launch, args=(version, username, ram))
        thread.daemon = True
        thread.start()


# Create HTML file separately to avoid quote issues
html_file = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Eclipse Launcher</title>
<style>
:root {
--theme-primary: #a855f7;
--theme-secondary: #8b5cf6;
--bg-primary: #0a0a0f;
--bg-secondary: rgba(20, 20, 30, 0.8);
--bg-tertiary: rgba(30, 30, 45, 0.6);
--text-primary: #e0e0e0;
--text-secondary: #b4b4b4;
--text-tertiary: #888;
--border-color: rgba(139, 92, 246, 0.3);
}
:root.light-mode {
--bg-primary: #f0f0f5;
--bg-secondary: rgba(255, 255, 255, 0.9);
--bg-tertiary: rgba(240, 240, 250, 0.8);
--text-primary: #1a1a1a;
--text-secondary: #4a4a4a;
--text-tertiary: #6a6a6a;
--border-color: rgba(139, 92, 246, 0.4);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
background: var(--bg-primary);
height: 100vh;
display: flex;
justify-content: center;
align-items: center;
color: var(--text-primary);
overflow: hidden;
transition: background 0.3s;
}
body::before {
content: '';
position: fixed;
top: 0; left: 0;
width: 100%; height: 100%;
background: radial-gradient(ellipse at top, var(--theme-primary)15, transparent),
radial-gradient(ellipse at bottom, var(--theme-primary)10, transparent);
pointer-events: none;
opacity: 0.3;
}
.container {
background: var(--bg-secondary);
backdrop-filter: blur(10px);
border-radius: 20px;
padding: 30px;
width: 650px;
max-height: 90vh;
overflow-y: auto;
box-shadow: 0 8px 32px 0 var(--border-color);
border: 1px solid var(--border-color);
position: relative;
z-index: 1;
transition: background 0.3s, border 0.3s;
}
.header {
display: flex;
align-items: center;
gap: 15px;
margin-bottom: 20px;
}
.player-head {
width: 48px; height: 48px;
background: var(--bg-tertiary);
border: 2px solid var(--theme-primary);
border-radius: 8px;
display: flex;
align-items: center;
justify-content: center;
font-weight: bold;
color: var(--theme-primary);
font-size: 20px;
box-shadow: 0 4px 10px var(--border-color);
transition: all 0.3s;
flex-shrink: 0;
overflow: hidden;
}
.player-head img {
width: 100%; height: 100%;
object-fit: cover;
}
.header-content { flex: 1; }
h1 {
text-align: left;
margin-bottom: 15px;
font-size: 28px;
background: linear-gradient(135deg, var(--theme-primary), var(--theme-secondary));
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
}
.tabs {
display: flex;
gap: 10px;
margin-bottom: 20px;
border-bottom: 2px solid var(--border-color);
}
.tab {
padding: 10px 20px;
background: transparent;
border: none;
color: var(--text-tertiary);
cursor: pointer;
transition: all 0.3s;
font-size: 14px;
font-weight: 600;
border-bottom: 2px solid transparent;
margin-bottom: -2px;
}
.tab:hover { color: var(--theme-primary); }
.tab.active {
color: var(--theme-primary);
border-bottom-color: var(--theme-primary);
}
.tab-content { display: none; }
.tab-content.active { display: block; }
.form-group { margin-bottom: 20px; }
label {
display: block;
margin-bottom: 8px;
font-weight: 600;
font-size: 13px;
color: var(--text-secondary);
}
input, select {
width: 100%;
padding: 12px;
border: 1px solid var(--border-color);
border-radius: 10px;
background: var(--bg-tertiary);
color: var(--text-primary);
font-size: 14px;
outline: none;
transition: all 0.3s;
}
.filter-buttons {
display: flex;
gap: 10px;
margin-bottom: 10px;
flex-wrap: wrap;
}
.filter-btn {
padding: 8px 16px;
background: var(--bg-tertiary);
border: 1px solid var(--border-color);
border-radius: 8px;
color: var(--text-secondary);
cursor: pointer;
font-size: 12px;
transition: all 0.3s;
}
.filter-btn:hover {
border-color: var(--theme-primary);
color: var(--theme-primary);
}
.filter-btn.active {
background: var(--border-color);
border-color: var(--theme-primary);
color: var(--theme-primary);
}
.slider-container { position: relative; }
.slider {
width: 100%;
height: 6px;
border-radius: 5px;
background: var(--border-color);
outline: none;
-webkit-appearance: none;
}
.slider::-webkit-slider-thumb {
-webkit-appearance: none;
width: 18px; height: 18px;
border-radius: 50%;
background: var(--theme-primary);
cursor: pointer;
}
.slider-value {
position: absolute;
right: 0; top: -25px;
color: var(--theme-primary);
font-weight: 600;
font-size: 14px;
}
button {
width: 100%;
padding: 14px;
background: linear-gradient(135deg, var(--theme-primary), var(--theme-secondary));
border: none;
border-radius: 10px;
color: #fff;
font-size: 16px;
font-weight: 600;
cursor: pointer;
transition: all 0.3s;
margin-top: 10px;
}
button:hover {
transform: translateY(-2px);
}
.danger-btn {
background: linear-gradient(135deg, #ef4444, #dc2626);
}
.progress-container {
margin-top: 20px;
display: none;
}
.progress-bar {
width: 100%;
height: 30px;
background: var(--bg-tertiary);
border-radius: 15px;
overflow: hidden;
border: 1px solid var(--border-color);
}
.progress-fill {
height: 100%;
background: linear-gradient(90deg, var(--theme-primary), var(--theme-secondary));
width: 0%;
transition: width 0.3s;
display: flex;
align-items: center;
justify-content: center;
font-weight: 600;
font-size: 12px;
}
.status {
margin-top: 15px;
text-align: center;
font-size: 13px;
min-height: 20px;
color: var(--text-secondary);
}
.history-item {
background: var(--bg-tertiary);
border: 1px solid var(--border-color);
border-radius: 10px;
padding: 15px;
margin-bottom: 10px;
transition: all 0.3s;
cursor: pointer;
}
.history-item:hover {
border-color: var(--theme-primary);
transform: translateX(5px);
}
.history-version {
font-weight: 600;
color: var(--theme-primary);
font-size: 15px;
margin-bottom: 5px;
}
.history-details {
font-size: 12px;
color: var(--text-tertiary);
}
.empty-history {
text-align: center;
color: var(--text-tertiary);
padding: 40px;
font-size: 14px;
}
.theme-selector {
display: flex;
gap: 10px;
flex-wrap: wrap;
}
.theme-option {
flex: 1;
min-width: 80px;
padding: 12px;
border-radius: 10px;
cursor: pointer;
text-align: center;
font-size: 13px;
font-weight: 600;
transition: all 0.3s;
border: 2px solid transparent;
color: white;
}
.theme-purple { background: linear-gradient(135deg, #a855f7, #8b5cf6); }
.theme-blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.theme-green { background: linear-gradient(135deg, #10b981, #059669); }
.theme-red { background: linear-gradient(135deg, #ef4444, #dc2626); }
.theme-option.active {
border-color: #fff;
box-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
}
.switch-container {
display: flex;
align-items: center;
justify-content: space-between;
padding: 12px;
background: var(--bg-tertiary);
border-radius: 10px;
border: 1px solid var(--border-color);
}
.switch {
position: relative;
display: inline-block;
width: 50px; height: 26px;
}
.switch input { opacity: 0; width: 0; height: 0; }
.switch-slider {
position: absolute;
cursor: pointer;
top: 0; left: 0; right: 0; bottom: 0;
background-color: #ccc;
transition: 0.4s;
border-radius: 26px;
}
.switch-slider:before {
position: absolute;
content: "";
height: 18px; width: 18px;
left: 4px; bottom: 4px;
background-color: white;
transition: 0.4s;
border-radius: 50%;
}
input:checked + .switch-slider { background-color: var(--theme-primary); }
input:checked + .switch-slider:before { transform: translateX(24px); }
.tutorial-modal {
position: fixed;
top: 0; left: 0;
width: 100%; height: 100%;
background: rgba(0, 0, 0, 0.8);
display: flex;
justify-content: center;
align-items: center;
z-index: 1000;
}
.tutorial-content {
background: var(--bg-secondary);
border-radius: 20px;
padding: 40px;
max-width: 500px;
border: 1px solid var(--border-color);
text-align: center;
}
.tutorial-content h2 {
color: var(--theme-primary);
margin-bottom: 20px;
font-size: 28px;
}
.tutorial-content p {
color: var(--text-secondary);
margin-bottom: 15px;
line-height: 1.6;
font-size: 14px;
}
.tutorial-content ul {
text-align: left;
margin: 20px 0;
color: var(--text-secondary);
line-height: 1.8;
}
.tutorial-content li { margin-bottom: 10px; }
.settings-section { margin-bottom: 30px; }
.settings-section h3 {
color: var(--theme-primary);
font-size: 16px;
margin-bottom: 15px;
padding-bottom: 10px;
border-bottom: 1px solid var(--border-color);
}
</style>
</head>
<body>
<div id="tutorialModal" class="tutorial-modal" style="display: none;">
<div class="tutorial-content">
<h2>Welcome to Eclipse Launcher!</h2>
<p>Quick tutorial to get you started.</p>
<ul>
<li><strong>Launch Tab:</strong> Select version, enter username, allocate RAM, and launch!</li>
<li><strong>History Tab:</strong> View previous launches and relaunch them.</li>
<li><strong>Settings Tab:</strong> Customize theme, dark/light mode, manage data.</li>
</ul>
<button onclick="closeTutorial()">Start!</button>
</div>
</div>
<div class="container">
<div class="header">
<div class="player-head" id="playerHead"><span>👤</span></div>
<div class="header-content"><h1>Eclipse Launcher</h1></div>
</div>
<div class="tabs">
<button class="tab active" onclick="switchTab('launch', this)">Launch</button>
<button class="tab" onclick="switchTab('history', this)">History</button>
<button class="tab" onclick="switchTab('settings', this)">Settings</button>
</div>
<div id="launch" class="tab-content active">
<div class="form-group">
<label>Version Filter</label>
<div class="filter-buttons">
<button class="filter-btn active" onclick="filterVersions('release', this)">Release</button>
<button class="filter-btn" onclick="filterVersions('snapshot', this)">Snapshot</button>
<button class="filter-btn" onclick="filterVersions('old_beta', this)">Beta</button>
<button class="filter-btn" onclick="filterVersions('old_alpha', this)">Alpha</button>
</div>
</div>
<div class="form-group">
<label>Minecraft Version</label>
<select id="version"><option value="">Loading...</option></select>
</div>
<div class="form-group">
<label>Username</label>
<input type="text" id="username" placeholder="Enter username" onblur="updatePlayerHead()" />
</div>
<div class="form-group">
<label>RAM Allocation</label>
<div class="slider-container">
<span class="slider-value" id="ramValue">2 GB</span>
<input type="range" min="1" max="16" value="2" class="slider" id="ramSlider" oninput="updateRamValue(this.value)">
</div>
</div>
<button id="launchBtn" onclick="launchGame()">Launch Minecraft</button>
<div class="progress-container" id="progressContainer">
<div class="progress-bar">
<div class="progress-fill" id="progressFill">0%</div>
</div>
<div class="status" id="status"></div>
</div>
</div>
<div id="history" class="tab-content">
<div id="historyList"><div class="empty-history">No history yet</div></div>
</div>
<div id="settings" class="tab-content">
<div class="settings-section">
<h3>Appearance</h3>
<div class="form-group">
<label>Theme Color</label>
<div class="theme-selector">
<div class="theme-option theme-purple" onclick="changeTheme('purple')">Purple</div>
<div class="theme-option theme-blue" onclick="changeTheme('blue')">Blue</div>
<div class="theme-option theme-green" onclick="changeTheme('green')">Green</div>
<div class="theme-option theme-red" onclick="changeTheme('red')">Red</div>
</div>
</div>
<div class="form-group">
<div class="switch-container">
<label style="margin: 0;">Dark Mode</label>
<label class="switch">
<input type="checkbox" id="darkModeSwitch" onchange="toggleDarkMode()" checked>
<span class="switch-slider"></span>
</label>
</div>
</div>
</div>
<div class="settings-section">
<h3>Information</h3>
<div class="form-group">
<label>Launcher Directory</label>
<input type="text" id="launcherDir" readonly />
</div>
</div>
<div class="settings-section">
<h3>Danger Zone</h3>
<div class="form-group">
<button class="danger-btn" onclick="confirmResetData()">RESET LAUNCHER DATA</button>
</div>
<div class="form-group">
<button class="danger-btn" onclick="confirmDeleteInstances()">DELETE MINECRAFT INSTANCES</button>
</div>
</div>
</div>
</div>
<script>
var allVersions = {};
var currentFilter = 'release';

function closeTutorial() {
document.getElementById('tutorialModal').style.display = 'none';
if (window.pywebview) pywebview.api.mark_tutorial_complete();
}

function loadVersions(filter) {
var select = document.getElementById('version');
select.innerHTML = '<option value="">Select a version</option>';
var versions = allVersions[filter] || [];
for (var i = 0; i < versions.length; i++) {
var opt = document.createElement('option');
opt.value = versions[i];
opt.textContent = versions[i];
select.appendChild(opt);
}
}

function filterVersions(type, el) {
currentFilter = type;
loadVersions(type);
var btns = document.querySelectorAll('.filter-btn');
for (var i = 0; i < btns.length; i++) btns[i].classList.remove('active');
if (el) el.classList.add('active');
}

function switchTab(name, el) {
var contents = document.querySelectorAll('.tab-content');
for (var i = 0; i < contents.length; i++) contents[i].classList.remove('active');
var tabs = document.querySelectorAll('.tab');
for (var i = 0; i < tabs.length; i++) tabs[i].classList.remove('active');
document.getElementById(name).classList.add('active');
if (el) el.classList.add('active');
}

function updateRamValue(val) {
document.getElementById('ramValue').textContent = val + ' GB';
}

function launchGame() {
var ver = document.getElementById('version').value;
var user = document.getElementById('username').value;
var ram = parseInt(document.getElementById('ramSlider').value);
if (!ver || !user) { alert('Please select version and username'); return; }
document.getElementById('launchBtn').disabled = true;
document.getElementById('progressContainer').style.display = 'block';
if (window.pywebview) pywebview.api.launch({version: ver, username: user, ram: ram});
}

function updateProgress(pct, curr, max) {
var fill = document.getElementById('progressFill');
fill.style.width = pct + '%';
fill.textContent = pct + '%';
}

function updateStatus(msg) {
document.getElementById('status').textContent = msg;
if (msg.indexOf('successfully') !== -1 || msg.indexOf('Error') !== -1) {
setTimeout(function() { document.getElementById('launchBtn').disabled = false; }, 2000);
}
}

function loadHistory(hist) {
var list = document.getElementById('historyList');
if (!hist || hist.length === 0) {
list.innerHTML = '<div class="empty-history">No history yet</div>';
return;
}
list.innerHTML = '';
for (var i = 0; i < hist.length; i++) {
var entry = hist[i];
var item = document.createElement('div');
item.className = 'history-item';
item.onclick = (function(v, u) {
return function() {
document.getElementById('version').value = v;
document.getElementById('username').value = u;
updatePlayerHead();
switchTab('launch', document.querySelectorAll('.tab')[0]);
};
})(entry.version, entry.username);
var d = new Date(entry.timestamp);
item.innerHTML = '<div class="history-version">' + entry.version + '</div><div class="history-details">Username: ' + entry.username + ' - ' + d.toLocaleDateString() + '</div>';
list.appendChild(item);
}
}

function changeTheme(theme, save) {
if (save === undefined) save = true;
var themes = {
purple: {p: '#a855f7', s: '#8b5cf6'},
blue: {p: '#3b82f6', s: '#2563eb'},
green: {p: '#10b981', s: '#059669'},
red: {p: '#ef4444', s: '#dc2626'}
};
var c = themes[theme];
document.documentElement.style.setProperty('--theme-primary', c.p);
document.documentElement.style.setProperty('--theme-secondary', c.s);
var opts = document.querySelectorAll('.theme-option');
for (var i = 0; i < opts.length; i++) opts[i].classList.remove('active');
var btn = document.querySelector('.theme-' + theme);
if (btn) btn.classList.add('active');
if (save && window.pywebview) pywebview.api.update_theme(theme);
}

function toggleDarkMode() {
var dark = document.getElementById('darkModeSwitch').checked;
if (dark) document.documentElement.classList.remove('light-mode');
else document.documentElement.classList.add('light-mode');
if (window.pywebview) pywebview.api.update_dark_mode(dark);
}

function confirmResetData() {
if (confirm('WARNING: Delete all launcher settings?')) {
if (window.pywebview) {
pywebview.api.reset_launcher_data().then(function(r) {
if (r.success) { alert(r.message); location.reload(); }
else alert(r.message);
});
}
}
}

function confirmDeleteInstances() {
if (confirm('DANGER: Delete all Minecraft instances?')) {
if (confirm('FINAL WARNING: Cannot be undone!')) {
if (window.pywebview) {
pywebview.api.delete_minecraft_instances().then(function(r) {
if (r.success) { alert(r.message); location.reload(); }
else alert(r.message);
});
}
}
}
}

function updatePlayerHead() {
var user = document.getElementById('username').value.trim();
var head = document.getElementById('playerHead');
if (!user) { head.innerHTML = '<span>👤</span>'; return; }
if (window.pywebview) {
pywebview.api.get_uuid(user).then(function(uuid) {
if (uuid) {
var img = document.createElement('img');
img.src = 'https://crafatar.com/avatars/' + uuid + '?size=100';
img.onerror = function() { head.innerHTML = '<span>👤</span>'; };
head.innerHTML = '';
head.appendChild(img);
} else {
head.innerHTML = '<span>❓</span>';
}
}).catch(function() { head.innerHTML = '<span>👤</span>'; });
}
}

window.addEventListener('pywebviewready', function() {
pywebview.api.get_versions().then(function(v) {
allVersions = v;
loadVersions(currentFilter);
});
pywebview.api.get_config().then(function(cfg) {
document.getElementById('username').value = cfg.last_username || '';
document.getElementById('ramSlider').value = cfg.ram_allocation || 2;
updateRamValue(cfg.ram_allocation || 2);
loadHistory(cfg.launch_history || []);
document.getElementById('launcherDir').value = cfg.launcher_directory || '';
if (cfg.theme) changeTheme(cfg.theme, false);
if (cfg.dark_mode !== undefined) {
document.getElementById('darkModeSwitch').checked = cfg.dark_mode;
if (!cfg.dark_mode) document.documentElement.classList.add('light-mode');
}
if (!cfg.tutorial_shown) document.getElementById('tutorialModal').style.display = 'flex';
if (cfg.last_username) updatePlayerHead();
});
});
</script>
</body>
</html>
"""

# Create and run the launcher
if __name__ == '__main__':
    launcher = MinecraftLauncher()
    launcher.config['launcher_directory'] = minecraft_directory

    launcher.window = webview.create_window(
        'Eclipse Launcher',
        html=html_file,
        js_api=launcher,
        width=700,
        height=650,
        resizable=False
    )
    webview.start(debug=True)