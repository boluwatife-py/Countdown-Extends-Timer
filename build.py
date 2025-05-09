import PyInstaller.__main__
import os
import sys

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define the files to include
files_to_include = [
    'setup.html',
    'countdown.html',
    'tailwind.js',
    'icon.ico'
]

# Check if all files exist
for file in files_to_include:
    file_path = os.path.join(current_dir, file)
    if not os.path.exists(file_path):
        print(f"Error: {file} not found in {current_dir}")
        sys.exit(1)

# Create the --add-data arguments
add_data_args = []
for file in files_to_include:
    add_data_args.extend(['--add-data', f'{file};.'])


try:
    PyInstaller.__main__.run([
        os.path.join(current_dir, 'server.py'),
        '--onefile',
        '--noconsole',
        '--name=TimerServer',
        '--icon=icon.ico',
        *add_data_args
    ])
    print("Build completed successfully. Find TimerServer.exe in the dist folder.")
except Exception as e:
    print(f"Error during PyInstaller build: {e}")
    sys.exit(1)