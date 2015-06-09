#!/usr/bin/python
import rospy
from sensor_msgs.msg import NavSatFix
from geometry_msgs.msg import Vector3
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu
from geometry_msgs.msg import Quaternion
import tf
import numpy

import warnings
import math

curTime = rospy.Time()
curRoll = float(0.0)
curPitch = float(0.0)
curYaw = float(0.0)
lastYaw = float(0.0)
lastPitch = float(0.0)
lastRoll = float(0.0)

'''
uint8 COVARIANCE_TYPE_UNKNOWN=0
uint8 COVARIANCE_TYPE_APPROXIMATED=1
uint8 COVARIANCE_TYPE_DIAGONAL_KNOWN=2
uint8 COVARIANCE_TYPE_KNOWN=3
std_msgs/Header header
  uint32 seq
  time stamp
  string frame_idvelodyne
sensor_msgs/NavSatStatus status
  int8 STATUS_NO_FIX=-1
  int8 STATUS_FIX=0
  int8 STATUS_SBAS_FIX=1
  int8 STATUS_GBAS_FIX=2
  uint16 SERVICE_GPS=1
  uint16 SERVICE_GLONASS=2
  uint16 SERVICE_COMPASS=4
  uint16 SERVICE_GALILEO=8
  int8 status
  uint16 service
float64 latitude
float64 longitude
float64 altitude
float64[9] position_covariance
uint8 position_covariance_type
'''
   
def parse_novatelINSPVA(insString):
    #print "++++instring:",insString
    gnssWeek = insString[0] # GNSS week 
    secondsFromWeek = insString[1] # Seconds from week start
    latitude = insString[2] # Latitude (WGS84)
    longitude = insString[3] # Longitude (WGS84)
    heightMSL = insString[4] # Ellipsoidal Height (WGS84) [m]
    velcnsY = insString[5] # Velocity in northerly direction [m/s] (negative for south)
    velcnsX = insString[6] # Velocity in easterly direction [m/s] (negative for west)
    velcnsZ = insString[7] # Velocity in upward direction [m/s]
    cnsRoll = float(insString[8])*(3.14159265/180) # yaw/azimuth - Right-handed rotation from local level around Z-axis -- changed from degress to radians (pi/180 deg)
    cnsPitch = float(insString[9])*(3.14159265/180)  # roll - (neg) Right-handed rotation from local level around y-axis  -- changed from degress to radians (pi/180 deg)
    cnsYaw = float(insString[10])*(3.14159265/180)  # pitch -Right-handed rotation from local level around x-axis  -- changed from degress to radians (pi/180 deg)
    inertialStatus = insString[11].split('*')[0] # Inertial status
   
    #print "inertialStatus",inertialStatus
    fix_msg = NavSatFix()
    fix_msg.header.stamp = rospy.get_rostime()
    fix_msg.header.frame_id = 'gps_frame'
    fix_msg.latitude = float(latitude)
    fix_msg.longitude = float(longitude)
    fix_msg.altitude = float(heightMSL)

    fix_msg.position_covariance = [0.01,0.0,0.0,0.0,0.01,0.0,0.0,0.0,999.0]
    fix_msg.position_covariance_type = 1
    #print "lat, long, alt:" + str(fix_msg.latitude)+ " , "+ str(fix_msg.longitude)+" , " + str(fix_msg.altitude)
    global curTime
    global curRoll
    global curYaw
    global curPitch
    global lastRoll
    global lastYaw
    global lastPitch

    #cns to imu coordinate sytem conversion --> cnsX = -imuY, cnsY = imuX, cnsZ = imuZ
    #imuY comes in as negative of value --> cancels out negative conversion
    imuRoll = cnsPitch
    imuPitch = cnsRoll
    imuYaw = -1*cnsYaw   
    
    lastYaw = curYaw
    curYaw = imuYaw
    lastPitch = curPitch
    curPitch = imuPitch
    lastRoll = curRoll
    curRoll   = imuRoll

    lastTime = curTime    
    curTime = rospy.Time.now()
    deltime = (curTime-lastTime).to_sec()

    imu_msg = Imu()
    imu_msg.header.stamp = curTime
    imu_msg.header.frame_id = 'imu_frame'
    imu_msg.linear_acceleration.x = float(velcnsY)#*.05/pow(2,15)
    imu_msg.linear_acceleration.y = float(velcnsX)*-1#*.05/pow(2,15)
    imu_msg.linear_acceleration.z = float(velcnsZ)#*.05/pow(2,15)
    imu_msg.linear_acceleration_covariance = [0.1,0.0,0.0,0.0,0.1,0.0,0.0,0.0,0.1]
    #imu_msg.orientation_covariance.x = float(angcnsY)
    euler = Vector3(curRoll, curPitch, curYaw)
    #euler = vector_norm(euler)
    quaternion = tf.transformations.quaternion_from_euler(curRoll, curPitch, curYaw)
    #type(pose) = geometry_msgs.msg.Pose
    imu_msg.orientation.x = quaternion[0]
    imu_msg.orientation.y = quaternion[1]
    imu_msg.orientation.z = quaternion[2]
    imu_msg.orientation.w = quaternion[3]
    imu_msg.orientation_covariance = [0.1,0.0,0.0,0.0,0.1,0.0,0.0,0.0,0.1]
    imu_msg.angular_velocity.x = (curPitch-lastPitch)/deltime
    imu_msg.angular_velocity.y = (curRoll-lastRoll)/deltime
    imu_msg.angular_velocity.z = (curYaw-lastYaw)/deltime
    imu_msg.angular_velocity_covariance = [0.1,0.0,0.0,0.0,0.1,0.0,0.0,0.0,0.1]
    #velx = float(velEast)*.05/pow(2,15)
    #vely = float(velNorth)*.05/pow(2,15)
    #velz = float(velUp)*.05/pow(2,15)
    #imu_msg = Vector3(velx,vely,velz,pitch,roll)
    #imu_msg.orientation.w = 0.01
    outHeader = "gnssWeek secondsFromWeek latitude longitude heightMSL velcnsY velcnsX velcnsZ," 
    outHeader += "cnsRoll cnsPitch cnsYaw inertialStatus"
    outString = insString[0],insString[1],insString[2],insString[3],insString[4],insString[5],insString[6],
    outString +=  insString[7],insString[8],insString[9],insString[10],insString[11].split('*')[0] # Inertial status

    retrnList = [imu_msg, fix_msg]
    return retrnList
    #TODO put data into a ROS MSG and return it

# Below is the test code
if __name__ == "__main__":
    rawGPSstring = '#BESTGPSPOSA,COM1,0,85.5,FINESTEERING,1815,408756.000,00000000,8505,11526;\
    SOL_COMPUTED,SINGLE,41.39183389839,-73.95306269372,32.9551,-32.2000,WGS84,1.7972,1.3207,3.3414,\
    "",0.000,0.000,10,10,10,0,0,02,00,01*1904fda5'
    rawINSPVstring = '#INSPVAA,COM1,0,86.0,FINESTEERING,1815,408756.500,00000000,54e2,11526;1815,\
    408756.500000000,-90.00000000000,0.00000000000,-6356752.3142,0.0000,0.0000,0.0000,0.000000000,\
    0.000000000,0.000000000,INS_ALIGNING*6666667b'
    rawIMUString = '%RAWIMUSA,1815,407772.000;1815,407771.985103333,00000077,63811,-6290,6253,7,\
    -31,14*2d2a4cff'
    
    gpsPub = rospy.Publisher('fix', NavSatFix, queue_size=1)
    rospy.init_node('novatel_CNS5000', anonymous=True)
    rate = rospy.Rate(5) # 10hz
        
    def novatel_publisher(inString):  
        if (inString.split(",")[0] == "#BESTGPSPOSA"): # check if this the gps message
            gpsData = rawGPSstring.split(';')[1] # split the header and message
            gpsData = gpsData.split(',') # split on message fields
            out_msg = parse_novatelGPS(gpsData)
            gpsPub.publish(out_msg)

        elif (inString.split(",")[0] == "%RAWIMUSA"): # check if this the IMU message     
            imuData = rawIMUString.split(';')[1] # split the header and message
            imuData = imuData.split(',') # split on message fields
            parse_novatelIMU(imuData)
            #TODO make a publisher for rawimu

        elif (inString.split(",")[0] == "#INSPVAA"): # check if this the INSPVA message    
            insData = rawINSPVstring.split(';')[1] # split the header and message
            insData = insData.split(',') # split on message fields
            parse_novatelINSPVA(insData)
            #TODO make a publisher for INSPVA
    
    while not rospy.is_shutdown():  
        novatel_publisher(rawGPSstring)
        novatel_publisher(rawINSPVstring)
        novatel_publisher(rawIMUString)

    
