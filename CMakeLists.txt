cmake_minimum_required(VERSION 3.10)
project(TimerServer)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Ensure the toolchain is MinGW-w64 and 64-bit
if(NOT MINGW)
    message(FATAL_ERROR "This project requires MinGW-w64")
endif()
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "This project must be built for 64-bit (Win64)")
endif()

# Enable Unicode support
add_definitions(-D_UNICODE -DUNICODE)

# Fully static build (no DLLs required)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -static-libgcc -static-libstdc++")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static -static-libgcc -static-libstdc++ -s")

# Source files
set(SOURCES main.cpp resource.rc)

# Minimal header-only HTTP server support
add_library(httplib INTERFACE)
target_include_directories(httplib INTERFACE ${CMAKE_SOURCE_DIR})

# Create the executable
add_executable(TimerServer WIN32 ${SOURCES})
target_link_libraries(TimerServer PRIVATE httplib ws2_32 shell32 user32 kernel32 comctl32)