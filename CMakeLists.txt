cmake_minimum_required(VERSION 3.10)
project(TimerServer)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT MINGW)
    message(FATAL_ERROR "This project requires MinGW-w64")
endif()
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "This project must be built for 64-bit (Win64)")
endif()

add_definitions(-D_UNICODE -DUNICODE)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -static-libgcc -static-libstdc++")

set(SOURCES main.cpp resource.rc)
add_library(httplib INTERFACE)
target_include_directories(httplib INTERFACE ${CMAKE_SOURCE_DIR})
add_executable(TimerServer WIN32 ${SOURCES})
target_link_libraries(TimerServer PRIVATE httplib ws2_32 shell32 user32 kernel32 comctl32)