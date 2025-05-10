#include <winsock2.h>
#include <windows.h>
#include <shellapi.h>
#include <string>
#include <thread>
#include <filesystem>
#include <fstream>
#include <httplib.h> // Header-only HTTP library
#include "resource.h" // For embedded resources

#define MUTEX_NAME L"TimerServerMutex"
#define PORT 3000
#define WM_TRAYICON (WM_USER + 1)
#define ID_TRAY_EXIT 1000

// Global variables
NOTIFYICONDATA nid = { sizeof(NOTIFYICONDATA) };
httplib::Server svr;
std::wstring temp_dir;
std::thread server_thread;

// Logging function (minimal, to file)
void log(const std::string& message) {
    std::ofstream log_file(std::string(getenv("USERPROFILE")) + "\\TimerServer.log", std::ios::app);
    if (log_file.is_open()) {
        auto now = std::time(nullptr);
        char timestamp[32];
        std::strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", std::localtime(&now));
        log_file << "[" << timestamp << "] " << message << "\n";
        log_file.close();
    }
}

// Extract embedded resource to temp file
bool extract_resource(int resource_id, const std::wstring& filename) {
    HRSRC hResource = FindResource(NULL, MAKEINTRESOURCE(resource_id), RT_RCDATA);
    if (!hResource) {
        log("Error: Resource ID " + std::to_string(resource_id) + " not found");
        return false;
    }
    HGLOBAL hMemory = LoadResource(NULL, hResource);
    if (!hMemory) {
        log("Error: Could not load resource ID " + std::to_string(resource_id));
        return false;
    }
    DWORD dwSize = SizeofResource(NULL, hResource);
    LPVOID lpAddress = LockResource(hMemory);
    std::ofstream out((std::filesystem::path(temp_dir) / filename).string(), std::ios::binary);
    if (!out.is_open()) {
        log("Error: Could not create file " + std::string(filename.begin(), filename.end()));
        return false;
    }
    out.write(static_cast<const char*>(lpAddress), dwSize);
    out.close();
    return true;
}

// Setup temporary directory and extract resources
bool setup_temp_directory() {
    WCHAR temp_path[MAX_PATH];
    GetTempPathW(MAX_PATH, temp_path);
    WCHAR temp_dir_path[MAX_PATH];
    GetTempFileNameW(temp_path, L"TSR", 0, temp_dir_path);
    DeleteFileW(temp_dir_path); // Remove temp file, we need a directory
    if (!CreateDirectoryW(temp_dir_path, NULL)) {
        log("Error: Could not create temp directory");
        return false;
    }
    temp_dir = temp_dir_path;
    log("Created temp directory: " + std::string(temp_dir.begin(), temp_dir.end()));

    // Extract embedded resources
    if (!extract_resource(IDR_SETUP_HTML, L"setup.html") ||
        !extract_resource(IDR_COUNTDOWN_HTML, L"countdown.html") ||
        !extract_resource(IDR_TAILWIND_JS, L"tailwind.js")) {
        log("Error: Failed to extract resources");
        return false;
    }
    return true;
}

// Cleanup temporary directory
void cleanup_temp_directory() {
    if (!temp_dir.empty() && std::filesystem::exists(temp_dir)) {
        try {
            std::filesystem::remove_all(temp_dir);
            log("Cleaned up temp directory: " + std::string(temp_dir.begin(), temp_dir.end()));
        }
        catch (const std::exception& e) {
            log("Error cleaning up temp directory: " + std::string(e.what()));
        }
    }
}

// Cleanup system tray icon
void cleanup_system_tray() {
    if (Shell_NotifyIcon(NIM_DELETE, &nid)) {
        log("System tray icon removed successfully");
    } else {
        log("Error: Failed to remove system tray icon");
    }
}

// System tray window procedure
LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_TRAYICON:
        if (lParam == WM_RBUTTONDOWN) {
            POINT pt;
            GetCursorPos(&pt);
            HMENU hMenu = CreatePopupMenu();
            AppendMenuW(hMenu, MF_STRING, ID_TRAY_EXIT, L"Exit");
            SetForegroundWindow(hwnd);
            TrackPopupMenu(hMenu, TPM_LEFTALIGN, pt.x, pt.y, 0, hwnd, NULL);
            DestroyMenu(hMenu);
        }
        break;
    case WM_COMMAND:
        if (LOWORD(wParam) == ID_TRAY_EXIT) {
            log("Exit command received from system tray");
            
            // Stop the server and wait for it to fully stop
            log("Stopping server...");
            svr.stop();
            
            // Wait for server thread to finish
            if (server_thread.joinable()) {
                log("Waiting for server thread to finish...");
                server_thread.join();
                log("Server thread joined");
            }
            
            // Clean up system tray icon
            cleanup_system_tray();
            
            // Clean up temporary directory
            cleanup_temp_directory();
            
            log("Exiting application");
            // Destroy the window which will trigger WM_DESTROY
            DestroyWindow(hwnd);
            return 0;
        }
        break;
    case WM_DESTROY:
        // Ensure tray icon is removed when window is destroyed
        cleanup_system_tray();
        // Post quit message to exit message loop cleanly
        PostQuitMessage(0);
        break;
    default:
        return DefWindowProc(hwnd, msg, wParam, lParam);
    }
    return 0;
}

// Create a hidden window for system tray messages
HWND create_tray_window(HINSTANCE hInstance) {
    WNDCLASSEXW wc = { sizeof(WNDCLASSEXW) };
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = L"TimerServerTrayClass";
    RegisterClassExW(&wc);

    HWND hwnd = CreateWindowW(L"TimerServerTrayClass", L"TimerServer", 0, 0, 0, 0, 0,
                             NULL, NULL, hInstance, NULL);
    if (!hwnd) {
        log("Error: Failed to create tray window");
    }
    return hwnd;
}

// Setup system tray
bool setup_system_tray(HINSTANCE hInstance, HWND hwnd) {
    nid.cbSize = sizeof(NOTIFYICONDATA);
    nid.hWnd = hwnd;
    nid.uID = 1;
    nid.uFlags = NIF_MESSAGE | NIF_TIP | NIF_ICON;
    nid.uCallbackMessage = WM_TRAYICON;
    // Load the icon from resources
    nid.hIcon = LoadIcon(hInstance, MAKEINTRESOURCE(IDI_ICON1));
    if (!nid.hIcon) {
        log("Error: Failed to load icon IDI_ICON1, using default application icon");
        nid.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    }
    wcscpy_s(nid.szTip, L"Timer Server");
    if (!Shell_NotifyIcon(NIM_ADD, &nid)) {
        log("Error: Failed to add system tray icon");
        return false;
    }
    log("System tray icon added successfully");
    return true;
}

// HTTP server setup
void run_server() {
    std::string temp_dir_str(temp_dir.begin(), temp_dir.end());
    
    // Set connection timeouts
    svr.set_read_timeout(std::chrono::seconds(1));        // 1 second read timeout
    svr.set_write_timeout(std::chrono::seconds(1));       // 1 second write timeout
    
    svr.Get("/", [&](const httplib::Request&, httplib::Response& res) {
        std::ifstream file(temp_dir_str + "\\setup.html", std::ios::binary);
        if (file) {
            std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
            res.set_content(content, "text/html");
        }
        else {
            res.status = 500;
            res.set_content("Internal Server Error", "text/plain");
        }
    });

    svr.Get("/countdown", [&](const httplib::Request&, httplib::Response& res) {
        std::ifstream file(temp_dir_str + "\\countdown.html", std::ios::binary);
        if (file) {
            std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
            res.set_content(content, "text/html");
        }
        else {
            res.status = 500;
            res.set_content("Internal Server Error", "text/plain");
        }
    });

    svr.Get("/tailwind.js", [&](const httplib::Request&, httplib::Response& res) {
        std::ifstream file(temp_dir_str + "\\tailwind.js", std::ios::binary);
        if (file) {
            std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
            res.set_content(content, "application/javascript");
        }
        else {
            res.status = 500;
            res.set_content("Internal Server Error", "text/plain");
        }
    });

    log("Server starting on port " + std::to_string(PORT) + " (localhost)");
    // Bind to localhost (127.0.0.1) instead of all interfaces (0.0.0.0)
    if (!svr.listen("127.0.0.1", PORT)) {
        log("Error: Failed to start server on port " + std::to_string(PORT));
        MessageBoxW(NULL, L"Failed to start server. Please check if port 3000 is available.", L"TimerServer Error",
                    MB_OK | MB_ICONERROR);
        return;
    }
    log("Server started successfully on port " + std::to_string(PORT));
}

// Main function
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE, LPSTR, int) {
    log("Starting TimerServer");

    // Single-instance check
    HANDLE hMutex = CreateMutexW(NULL, FALSE, MUTEX_NAME);
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        log("TimerServer is already running");
        MessageBoxW(NULL, L"TimerServer is already running.", L"TimerServer",
                    MB_OK | MB_TOPMOST);
        CloseHandle(hMutex);
        return 1;
    }

    // Setup temporary directory
    if (!setup_temp_directory()) {
        log("Failed to setup temp directory");
        CloseHandle(hMutex);
        return 1;
    }

    // Create window for system tray
    HWND hwnd = create_tray_window(hInstance);
    if (!hwnd) {
        cleanup_temp_directory();
        CloseHandle(hMutex);
        return 1;
    }

    // Start HTTP server in a separate thread
    server_thread = std::thread(run_server);
    log("Debug: Server thread launched");

    // Setup system tray
    if (!setup_system_tray(hInstance, hwnd)) {
        svr.stop();
        if (server_thread.joinable()) {
            server_thread.join();
        }
        cleanup_temp_directory();
        CloseHandle(hMutex);
        DestroyWindow(hwnd);
        return 1;
    }

    // Message loop
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // Cleanup
    DestroyWindow(hwnd);
    CloseHandle(hMutex);
    return 0;
}