cmake_minimum_required(VERSION 3.10)
project(scenario_gazebo_plugins)

set(CMAKE_CXX_STANDARD 17)
find_package(gazebo REQUIRED)
include_directories(${GAZEBO_INCLUDE_DIRS})
link_directories(${GAZEBO_LIBRARY_DIRS})
list(APPEND CMAKE_CXX_FLAGS "${GAZEBO_CXX_FLAGS}")

add_library(scenario_wind_zone SHARED src/wind_zone_plugin.cpp)
target_link_libraries(scenario_wind_zone ${GAZEBO_LIBRARIES})

add_library(scenario_moving_obstacle SHARED src/moving_obstacle_plugin.cpp)
target_link_libraries(scenario_moving_obstacle ${GAZEBO_LIBRARIES})
