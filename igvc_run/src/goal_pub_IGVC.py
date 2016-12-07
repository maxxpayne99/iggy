#!/usr/bin/env python

""" Code modified by: Dominic Larkin 5FEB2016
    
    Command a robot to move autonomously among a number of goal locations defined in the map frame.
    Attempt to move to each location in succession.  Keep track of success rate, time elapsed, and 
    total distance traveled. The goal locations are determined by adding distances to the current
    location of the robot on the map.
    based on nav_test.py - Version 0.1 2012-01-10. Modified for use with West Point Robotics.
    Originaly created for the Pi Robot Project: http://www.pirobot.org
    Copyright (c) 2012 Patrick Goebel.  All rights reserved.
    Original License:
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.
"""
import csv
import roslib
import rospy
import actionlib
import time
from actionlib_msgs.msg import *
from geometry_msgs.msg import Pose, PoseWithCovarianceStamped, Point, Quaternion, Twist
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from sensor_msgs.msg import NavSatFix
from nav_msgs.msg import Odometry 
from random import sample
from math import pow, sqrt
from LatLongUTMconversion import LLtoUTM, UTMtoLL

global nav

def update_current_pose(current_pose):
    #rospy.loginfo("Current Pose is: (%.4f,%.4f)" %((current_pose.pose.pose.position.x),(current_pose.pose.pose.position.y)))
    try:
        nav.current_pose = current_pose
    except NameError:
        print "Still booting..."

def update_utm(current_latlong):
    #rospy.loginfo("Current Lat, Long is: (%f,%f)" %((current_latlong.latitude),(current_latlong.longitude)))
    try:
        nav.current_utm = LLtoUTM(23, current_latlong.latitude,current_latlong.longitude)
    except NameError:
        print "Still booting..."


class NavTest():
    def __init__(self):        
        rospy.init_node('nav_test', anonymous=True)        
        rospy.on_shutdown(self.shutdown)    

        # Subscribe to the move_base action server
	self.goal = MoveBaseGoal()
        self.move_base = actionlib.SimpleActionClient("move_base", MoveBaseAction)        
        rospy.loginfo("Waiting for move_base action server...")        
        # Wait 60 seconds for the action server to become available
        self.move_base.wait_for_server(rospy.Duration(60))        
        rospy.loginfo("Connected to move base server")        
           
        # Publisher to manually control the robot (e.g. to stop it)
        self.cmd_vel_pub = rospy.Publisher('cmd_vel', Twist, queue_size=1) 
        
        # A variable to hold the initial and current pose of the robot
        self.current_pose = Odometry()
        self.initial_pose = Odometry()
        self.current_utm = [] # return (UTMZone, UTMEasting, UTMNorthing)
        self.initial_utm = [] # return (UTMZone, UTMEasting, UTMNorthing)
        
        # Goal state return values
        self.goal_states = ['PENDING', 'ACTIVE', 'PREEMPTED', 
                       'SUCCEEDED', 'ABORTED', 'REJECTED',
                       'PREEMPTING', 'RECALLING', 'RECALLED',
                       'LOST']       

        rospy.Subscriber('/odom', Odometry, update_current_pose)
        rospy.Subscriber('/gps/fix', NavSatFix, update_utm)
	        
    def navigate(self):
        # Variables to keep track of success rate, running time,
        # and distance traveled
        n_goals = 0
        n_successes = 0
        distance_traveled = 0
        start_time = rospy.Time.now()
        running_time = 0
        
        # TODO Use Dynamic reconfig for this
        # How long in seconds should the robot pause at each location?
        rest_time = rospy.get_param("~rest_time", 10)
        
        # TODO set the state variable for current location as start location
        self.setInitialPose() # In the odom frame. TODO Should this be in map frame?
    
        # TODO getGoals in odom frame, make a list in odom frame. 
        goals=self.makeWaypointsIntoGoals('waypoints.csv')
    
        # Begin the main loop and run through a sequence of locations
        i = 0
        while not rospy.is_shutdown():                        
            # Keep track of the distance traveled.
            # TODO update the tolerance and pause time.
            cur_coord = goals[i][0]
            last_coord = goals[i-1][0]
            if i != 0:
                distance = sqrt(pow(cur_coord.position.x - last_coord.position.x, 2) +
                                pow(cur_coord.position.y - last_coord.position.y, 2))
            else:
                distance = sqrt(pow(cur_coord.position.x - self.initial_pose.pose.pose.position.x, 2) +
                                pow(cur_coord.position.y - self.initial_pose.pose.pose.position.y, 2))         
            # Set up the next goal location
            self.goal.target_pose.pose = cur_coord
            self.goal.target_pose.header.frame_id = 'map'
            self.goal.target_pose.header.stamp = rospy.Time.now()
            self.goal.target_pose.pose.orientation = self.initial_pose.pose.pose.orientation

            # Let the user know where the robot is going next
            rospy.loginfo("Going to: (%.4f,%.4f)" %(self.goal.target_pose.pose.position.x,self.goal.target_pose.pose.position.y))
            
            # Start the robot toward the next location
            self.move_base.send_goal(self.goal)
            
            # Allow 5 minutes to get there
            finished_within_time = self.move_base.wait_for_result(rospy.Duration(300)) 
            
            # Check for success or failure
            if not finished_within_time:
                self.move_base.cancel_goal()
                rospy.loginfo("Timed out achieving goal")
            else:
                state = self.move_base.get_state()
                if state == GoalStatus.SUCCEEDED:
                    rospy.loginfo("Goal succeeded!")
                    n_successes += 1
                    distance_traveled += distance
                    rospy.loginfo("State:" + str(state))
                else:
                  rospy.loginfo("Goal failed with error code: " + str(self.goal_states[state]))
            
            # How long have we been running?
            running_time = rospy.Time.now() - start_time
            running_time = running_time.secs / 60.0
            
            # Print a summary success/failure, distance traveled and time elapsed
            n_goals += 1
            rospy.loginfo("Success so far: " + str(n_successes) + "/" + 
                          str(n_goals) + " = " + 
                          str(100 * n_successes/n_goals) + "%")
            rospy.loginfo("Running time: %.2f min Distance: %.3f"  % (running_time,distance_traveled))
            # Increment the counters
            i += 1
            if (i >= len(goals)):
                rospy.signal_shutdown("NO MORE GOALS TO ACHIEVE")
            rospy.sleep(rest_time)

    def setInitialPose(self):            
        # Make sure we have the initial pose
        rospy.loginfo("Waiting for initial pose")
        # Get the initial pose from the robot
        rospy.wait_for_message('/odom', Odometry)
	while len(self.current_utm) != 3:
            time.sleep(1) 
        rospy.loginfo("Establishing initial position wait 10 seconds.")	
	easts=[]
	nrths=[]
	for i in range(1):
       	    utm_c=self.current_utm
	    print self.current_utm
	    easts.append(utm_c[1])
	    nrths.append(utm_c[2])
	    rospy.sleep(1.5)
	easting = sum(easts) / float(len(easts))
	northing = sum(nrths) / float(len(nrths))
        self.initial_pose = self.current_pose 
        self.initial_utm = [utm_c[0],easting,northing]
        rospy.loginfo("Initial pose found at (%.4f,%.4f)" %(self.initial_pose.pose.pose.position.x,self.initial_pose.pose.pose.position.y))               
	rospy.loginfo("Initial UTM at (%.4f, %.4f)" % (easting, northing) )
	print UTMtoLL(23, self.initial_utm[2], self.initial_utm[1], self.initial_utm[0])

    # Turn list of waypoints into Goals. Goals are coordinates in the robot odom frame.
    # TODO Look into makeing this in the map frame if map and odom frame diverge.
    def makeWaypointsIntoGoals(self, filename):
        log_directory = rospy.get_param("~log_directory", "~/")+"waypoints2Goals_log.csv"
        # Load and parse waypoints from file.
        wps = self.loadWaypoints(filename)
        goals=[]
        for waypointLat,waypointLong,search_duration,rest_duration in wps:
            goal_pose=Pose()
            (wpZone,wpEasting,wpNorthing)=LLtoUTM(23, waypointLat,waypointLong)
            print "Waypoint ll",waypointLat,waypointLong,"east,north", wpEasting,wpNorthing,"init",self.initial_utm
            goal_pose.position.x=(wpEasting - self.initial_utm[1]) # REP103 says x is east and y is north
            goal_pose.position.y=(wpNorthing - self.initial_utm[2])
            goals.append((goal_pose, search_duration, rest_duration))
        return goals
        
        '''
        (initZone,initEasting,initNorthing)=LLtoUTM(23, current_lat,current_long)
        outString = "lat,long,restTime,tolerance,zone,easting,northing,
        print outString
        outString = current_lat+','+current_long+','+rest_time+','+tolerance+','+initZone+','+initEasting+','+initNorthing
        print outString
        '''

    # Read from file the list of Lat,Long,Duration,Tolerance and put into a list of waypoints
    def loadWaypoints(self, filename):
        waypoints=[]
        with open(filename, mode='r') as infile:
            reader = csv.reader(infile)
            for row in reader:
                if row[0][0] != '#': # ignore commented out waypoints
                    print row[0],row[1]
                    waypoints.append((float(row[0]),float(row[1]),float(row[2]),float(row[3])))
        return waypoints
            
    def update_current_pose(self, current_pose):
        rospy.loginfo("Current Pose is: (%.4f,%.4f)" %((current_pose.pose.pose.position.x),(current_pose.pose.pose.position.y)))        
        self.current_pose = current_pose

    def update_utm(self, current_latlong):
        rospy.loginfo("Current Lat, Long is: (%f,%f)" %((current_latlong.latitude),(current_latlong.longitude)))        
        self.current_utm = LLtoUTM(23, current_latlong.latitude,current_latlong.longitude)

    def shutdown(self):
        rospy.loginfo("Stopping the robot...")
        self.move_base.cancel_goal()
        rospy.sleep(2)
        self.cmd_vel_pub.publish(Twist())
        rospy.sleep(1)

if __name__ == '__main__':
    global nav
    try:
        nav = NavTest()
        nav.navigate()
        
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("Navigation test finished.")
