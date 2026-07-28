import subprocess
import os

base_dir = r"C:\Users\DELL\Desktop\NoB-main\NoB-main\backend"

narrations = {
    r"media\audio\malleshwaram\01-circle.mp3": "Hello! Welcome to Malleshwaram. Start at the circle, once the edge of the original 1889 plague relocation extension.",
    r"media\audio\malleshwaram\02-market.mp3": "Hello! You are now at the 8th Cross Market. This flower and vegetable market gives the neighbourhood its rhythm every morning.",
    r"media\audio\malleshwaram\03-temple.mp3": "Hello! Welcome to Kadu Malleshwara Temple, the ancient temple this neighbourhood is named after.",
    r"media\audio\basavanagudi\01-bugle-rock.mp3": "Hello! Welcome to Bugle Rock Park, a three billion year old rock outcrop.",
    r"media\audio\basavanagudi\02-bull-temple.mp3": "Hello! Welcome to Bull Temple, home to one of the largest monolithic Nandi statues in India.",
    r"media\audio\cubbon\01-bandstand.mp3": "Hello! Welcome to the Cubbon Park Bandstand, built in 1927."
}

ps_script = """
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
"""

for rel_path, text in narrations.items():
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    # Ensure escaped quotes for PowerShell string
    clean_text = text.replace("'", "''")
    clean_path = full_path.replace("'", "''")
    ps_script += f"""
$synth.SetOutputToWaveFile('{clean_path}')
$synth.Speak('{clean_text}')
"""

ps_script += """
$synth.Dispose()
Write-Host "All audio files successfully generated!"
"""

ps_file = os.path.join(base_dir, "gen_audio.ps1")
with open(ps_file, "w", encoding="utf-8") as f:
    f.write(ps_script)

print("Running PowerShell Speech Synthesizer...")
res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)

if os.path.exists(ps_file):
    os.remove(ps_file)
