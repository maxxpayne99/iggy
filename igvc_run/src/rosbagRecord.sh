#!/bin/bash

rosbag record -O $HOME/catkin_ws/rosbags/imudata.bag /imu_data &
rosbag record -O $HOME/catkin_ws/rosbags/gps_fix.bag /gps/fix &
#rosbag record -O $HOME/catkin_ws/rosbags/enc_raw.bag /enc_raw &
rosbag record -O $HOME/catkin_ws/rosbags/right_camera.bag /camera/right/rgb &
rosbag record -O $HOME/catkin_ws/rosbags/left_camera.bag /camera/left/rgb &
rosbag record -O $HOME/catkin_ws/rosbags/raw_gpsImu.bag /raw_data &
rosbag record -O $HOME/catkin_ws/rosbags/pointcloud.bag /velodyne_points &
#rosbag record -O $HOME/catkin_ws/rosbags/output_ground.bag /segmenter_nodelet/output_ground &
#rosbag record -O $HOME/catkin_ws/rosbags/output_not_ ground.bag /segmenter_nodelet/output_not_ground &
rosbag record -O $HOME/catkin_ws/rosbags/triclops_points.bag /triclops/points &
# The below line captures all other relevant topics being published
rosbag record -a -O $HOME/catkin_ws/rosbags/other.bag -x "/imu_data|/gps/fix|/velodyne_points|/camera/(.*)|/raw_data|/segmenter_nodelet/(.*)|/triclops/points"
