cmake_minimum_required(VERSION 3.8)
project(amr_simulation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch worlds config urdf models
  DESTINATION share/${PROJECT_NAME})

install(PROGRAMS
  scripts/battery_sim_node.py
  DESTINATION lib/${PROJECT_NAME})

ament_package()
