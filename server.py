import http.server
import socketserver
import sys
import os
import traceback
from threading import Thread
import win32gui
import win32con
import win32event
import win32api
import winerror
import tempfile
import datetime
import pythoncom
import shutil
import win32ui

PORT = 3000
httpd = None
LOG_FILE = os.path.join(os.path.expanduser("~"), "TimerServer.log")
TEMP_DIR = None

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    if hasattr(sys, 'stdout') and sys.stdout is not None:
        print(f"[TimerServer] {log_message}")
    else:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_message + '\nDiagnosis: Consider checking antivirus settings or system load if delays persist.')
        except:
            pass

def show_popup():
    try:
        pythoncom.CoInitialize()
        icon_path = get_resource_path('icon.ico')
        flags = win32con.MB_OK | win32con.MB_ICONINFORMATION | win32con.MB_TOPMOST
        if os.path.exists(icon_path):
            flags |= win32con.MB_USERICON
            win32ui.MessageBox("TimerServer is already running.", "TimerServer", flags, icon_path)
        else:
            win32ui.MessageBox("TimerServer is already running.", "TimerServer", flags)
    except Exception as e:
        log(f"Error showing popup: {e}")
    finally:
        try:
            pythoncom.CoUninitialize()
        except:
            pass

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    full_path = os.path.join(base_path, relative_path)
    if not os.path.exists(full_path):
        log(f"Error: Resource does not exist: {full_path}")
    return full_path

def setup_temp_directory():
    global TEMP_DIR
    try:
        TEMP_DIR = tempfile.mkdtemp()
        log(f"Created temp directory: {TEMP_DIR}")
        required_files = ['setup.html', 'countdown.html', 'tailwind.js', 'icon.ico']
        missing_files = []
        for file in required_files:
            src_path = get_resource_path(file)
            if os.path.exists(src_path):
                try:
                    shutil.copy2(src_path, os.path.join(TEMP_DIR, file))
                except Exception as e:
                    log(f"Error copying {file}: {e}")
                    missing_files.append(file)
            else:
                missing_files.append(file)
        if missing_files:
            log(f"Error: Failed to copy or find files: {', '.join(missing_files)}")
            return False
        return True
    except Exception as e:
        log(f"Error setting up temp directory: {e}\n{traceback.format_exc()}")
        return False

def cleanup_temp_directory():
    global TEMP_DIR
    if TEMP_DIR and os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            log(f"Cleaned up temp directory: {TEMP_DIR}")
        except Exception as e:
            log(f"Error cleaning up temp directory: {e}")
        TEMP_DIR = None

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, directory=TEMP_DIR, **kwargs)
        except Exception as e:
            log(f"Error initializing handler: {e}\n{traceback.format_exc()}")
            raise

    def log_message(self, format, *args):
        message = format % args
        log(f"HTTP request: {message}")

    def do_GET(self):
        try:
            if self.path == '/':
                self.path = '/setup.html'
                log("Serving setup.html")
            elif self.path == '/countdown':
                self.path = '/countdown.html'
                log("Serving countdown.html")
            super().do_GET()
        except ConnectionAbortedError:
            pass
        except Exception as e:
            log(f"Error handling GET request: {e}\n{traceback.format_exc()}")
            self.send_error(500, "Internal Server Error")

def run_server():
    global httpd
    try:
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.ThreadingTCPServer(("", PORT), MyHandler)
        httpd.timeout = 0.005
        log(f"Server started on http://localhost:{PORT}")
        httpd.serve_forever()
    except OSError as e:
        if e.errno == 10048:
            log(f"Error: Port {PORT} is already in use")
        else:
            log(f"Error starting server: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    except Exception as e:
        log(f"Unexpected server error: {e}\n{traceback.format_exc()}")
        sys.exit(1)

def create_system_tray():
    try:
        pythoncom.CoInitialize()
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "TimerServer"
        wc.hbrBackground = win32con.COLOR_WINDOW
        wc.lpfnWndProc = wnd_proc
        win32gui.RegisterClass(wc)
        
        hwnd = win32gui.CreateWindow(
            wc.lpszClassName,
            "Timer Server",
            win32con.WS_OVERLAPPED | win32con.WS_SYSMENU,
            0, 0, 0, 0,
            0, 0, 0, None
        )
        
        icon_path = get_resource_path('icon.ico')
        icon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        if os.path.exists(icon_path):
            try:
                icon = win32gui.LoadImage(
                    0, icon_path, win32con.IMAGE_ICON, 0, 0, win32con.LR_LOADFROMFILE
                )
            except Exception as e:
                log(f"Error loading icon: {e}")
        
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        nid = (hwnd, 0, flags, win32con.WM_USER+20, icon, "Timer Server")
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        
        log("System tray icon created")
        return hwnd, nid
    except Exception as e:
        log(f"Error creating system tray: {e}\n{traceback.format_exc()}")
        return None, None
    finally:
        try:
            pythoncom.CoUninitialize()
        except:
            pass

def wnd_proc(hwnd, msg, wparam, lparam):
    try:
        if msg == win32con.WM_USER + 20 and lparam == win32con.WM_RBUTTONDOWN:
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1000, "Exit")
            pos = win32gui.GetCursorPos()
            win32gui.SetForegroundWindow(hwnd)
            win32gui.TrackPopupMenu(
                menu, win32con.TPM_LEFTALIGN, pos[0], pos[1], 0, hwnd, None
            )
            win32gui.DestroyMenu(menu)
        elif msg == win32con.WM_COMMAND and wparam == 1000:
            global httpd
            try:
                if httpd:
                    httpd.shutdown()
                    httpd.socket.close()
                    httpd.server_close()
                    log("Server shut down")
            except Exception as e:
                log(f"Error shutting down server: {e}")
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
                win32gui.DestroyWindow(hwnd)
                log("System tray icon removed")
            except Exception as e:
                log(f"Error removing system tray: {e}")
            cleanup_temp_directory()
            log("Exiting application")
            win32api.PostQuitMessage(0)
            os._exit(0)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    except Exception as e:
        log(f"Error in system tray handler: {e}\n{traceback.format_exc()}")
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def main():
    try:
        log("Starting TimerServer")
        mutex_name = "TimerServerMutex"
        mutex = win32event.CreateMutex(None, False, mutex_name)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            log("TimerServer is already running")
            show_popup()
            sys.exit(1)

        if not setup_temp_directory():
            log("Failed to setup temp directory")
            sys.exit(1)

        server_thread = Thread(target=run_server, daemon=True)
        try:
            server_thread.start()
            log("Server thread started")
        except Exception as e:
            log(f"Error starting server thread: {e}\n{traceback.format_exc()}")
            cleanup_temp_directory()
            sys.exit(1)
        
        hwnd, nid = create_system_tray()
        if not hwnd or not nid:
            if httpd:
                try:
                    httpd.shutdown()
                    httpd.socket.close()
                    httpd.server_close()
                    log("Server shut down due to system tray failure")
                except:
                    pass
            cleanup_temp_directory()
            log("Failed to create system tray")
            sys.exit(1)
        
        try:
            log("Entering message loop")
            win32gui.PumpMessages()
        except Exception as e:
            log(f"Error in message loop: {e}\n{traceback.format_exc()}")
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
                win32gui.DestroyWindow(hwnd)
                log("System tray icon removed")
            except:
                pass
            if httpd:
                try:
                    httpd.shutdown()
                    httpd.socket.close()
                    httpd.server_close()
                    log("Server shut down")
                except:
                    pass
            cleanup_temp_directory()
            sys.exit(0)
        finally:
            try:
                win32api.CloseHandle(mutex)
                log("Mutex released")
            except:
                pass
    except Exception as e:
        log(f"Critical error in main: {e}\n{traceback.format_exc()}")
        cleanup_temp_directory()
        sys.exit(1)

if __name__ == "__main__":
    main()