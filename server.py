import http.server
import socketserver
import sys
import os
from threading import Thread
import win32gui
import win32con
import win32event
import win32api
import winerror
import tempfile

PORT = 3000
httpd = None

def log(message):
    """Log messages during development or when console is available"""
    if hasattr(sys, 'stdout') and sys.stdout is not None:
        print(f"[TimerServer] {message}")

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    full_path = os.path.join(base_path, relative_path)
    log(f"Resolved resource path: {relative_path} -> {full_path}")
    return full_path

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.temp_dir = tempfile.mkdtemp()
        log(f"Created temp directory: {self.temp_dir}")
        try:
            required_files = ['setup.html', 'countdown.html', 'tailwind.js', 'icon.ico']
            missing_files = []
            for file in required_files:
                src_path = get_resource_path(file)
                if os.path.exists(src_path):
                    try:
                        with open(src_path, 'rb') as src:
                            dst_path = os.path.join(self.temp_dir, file)
                            with open(dst_path, 'wb') as dst:
                                dst.write(src.read())
                            log(f"Copied {file} to {dst_path}")
                    except Exception as e:
                        log(f"Error copying {file}: {e}")
                        missing_files.append(file)
                else:
                    log(f"Resource not found: {src_path}")
                    missing_files.append(file)
            if missing_files:
                log(f"Warning: Missing or failed to copy files: {', '.join(missing_files)}")
            super().__init__(*args, directory=self.temp_dir, **kwargs)
        except Exception as e:
            log(f"Error initializing handler: {e}")
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    for file in os.listdir(self.temp_dir):
                        os.remove(os.path.join(self.temp_dir, file))
                    os.rmdir(self.temp_dir)
                    log(f"Cleaned up temp directory: {self.temp_dir}")
                except:
                    pass
            raise

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
            log(f"Error handling GET request: {e}")
            self.send_error(500, "Internal Server Error")

def run_server():
    global httpd
    try:
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("", PORT), MyHandler)
        httpd.timeout = 0.05
        log(f"Server started on http://localhost:{PORT}")
        httpd.serve_forever()
    except OSError as e:
        if e.errno == 10048:  # Address already in use
            log(f"Error: Port {PORT} is already in use")
        else:
            log(f"Error starting server: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"Unexpected server error: {e}")
        sys.exit(1)

def create_system_tray():
    try:
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
        log(f"Error creating system tray: {e}")
        return None, None

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
            log("Exiting application")
            os._exit(0)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    except Exception as e:
        log(f"Error in system tray handler: {e}")
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def main():
    log("Starting TimerServer")
    # Single-instance check using mutex
    mutex_name = "TimerServerMutex"
    mutex = win32event.CreateMutex(None, False, mutex_name)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        log("TimerServer is already running")
        sys.exit(1)

    server_thread = Thread(target=run_server, daemon=True)
    try:
        server_thread.start()
        log("Server thread started")
    except Exception as e:
        log(f"Error starting server thread: {e}")
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
        log("Failed to create system tray")
        sys.exit(1)
    
    try:
        log("Entering message loop")
        while True:
            msg = win32gui.GetMessage(hwnd, 0, 0)
            if msg[0]:
                win32gui.TranslateMessage(msg[1])
                win32gui.DispatchMessage(msg[1])
    except Exception as e:
        log(f"Error in message loop: {e}")
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
        sys.exit(0)
    finally:
        try:
            win32api.CloseHandle(mutex)
            log("Mutex released")
        except:
            pass

if __name__ == "__main__":
    main()