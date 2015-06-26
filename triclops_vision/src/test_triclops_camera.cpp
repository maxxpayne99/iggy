#include <triclops.h>
#include <fc2triclops.h>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>

#include <stdio.h>
#include <stdlib.h>
#include <ros/ros.h>
#include <sensor_msgs/image_encodings.h>
#include "triclops_vision/typedefs.h"
#include "triclops_vision/sto3dpoints.h"
#include "triclops_vision/triclops_opencv.h"
#include "triclops_vision/LineFilter.h"

/* This is a program that tests the triclops camera driver and the triclops opencv code.
 * This test displays both the right and left camera images in the opencv highgui after
 * converting the camera triclops images into a opencv image.
 */

TriclopsError     te;

bool SHOW_OPENCV = true;

int main(int  argc, char **argv)
{
  LineFilter lf;
  TriclopsInput triclopsColorInput, triclopsMonoInput;
  TriclopsContext triclops;

  FC2::Camera camera;
  FC2::Image grabbedImage;

  camera.Connect();
  // configure camera
  if ( configureCamera( camera ) )
  {
      return EXIT_FAILURE;
  }

  // generate the Triclops context
  if ( generateTriclopsContext( camera, triclops ) )
  {
      return EXIT_FAILURE;
  }

  // Par 1 of 2 for grabImage method
  FC2::Error fc2Error = camera.StartCapture();
  if (fc2Error != FC2::PGRERROR_OK)
  {
      return FC2T::handleFc2Error(fc2Error);
  }

  // Get the camera info and print it out
  FC2::CameraInfo camInfo;
  fc2Error = camera.GetCameraInfo( &camInfo );
  if ( fc2Error != FC2::PGRERROR_OK )
  {
      std::cout << "Failed to get camera info from camera" << std::endl;
      return false;
  }
  else
  {
      ROS_INFO(">>>>> CAMERA INFO  Vendor: %s     Model: %s     Serail#: %d \n", camInfo.vendorName, camInfo.modelName, camInfo.serialNumber);
  }

  ros::init(argc, argv, "talker");
  ros::NodeHandle nh;
  ros::Rate loop_rate(10);
  ros::Publisher pc2_pub = nh.advertise<sensor_msgs::PointCloud2>("points", 0);

  // Container of Images used for processing
  ImageContainer imageContainer;

  while (ros::ok())
  {
    // Part 2 of 2 for grabImage method
    // this image contains both right and left images
    fc2Error = camera.RetrieveBuffer(&grabbedImage);
    if (fc2Error != FC2::PGRERROR_OK)
    {
        return FC2T::handleFc2Error(fc2Error);
    }

    // generate triclops inputs from grabbed image
    if ( generateTriclopsInput( grabbedImage, imageContainer, triclopsColorInput, triclopsMonoInput ))
        {
                    return EXIT_FAILURE;
        }

    // output image disparity image with subpixel interpolation
    TriclopsImage16 disparityImage16;

    // carry out the stereo pipeline
    if ( doStereo( triclops, triclopsMonoInput, disparityImage16 ) )
    {
                return EXIT_FAILURE;
    }

    cv::Mat      dispImage;
    cv::Mat      leftImage;
    cv::Mat      rightImage;
    convertTriclops2Opencv(imageContainer.bgru[0], rightImage);
    convertTriclops2Opencv(imageContainer.bgru[1], leftImage);
    convertTriclops2Opencv(disparityImage16, dispImage);
    bool SHOW_OPENCV = true;
    if (SHOW_OPENCV){
        cv::imshow("Image Disp", dispImage);
//        cv::imshow("Image Left", leftImage);
        cv::waitKey(3);
      }

    cv::Mat filtered_image;
    cv::vector<cv::Vec4i> lines;
    lf.findLines(leftImage, filtered_image, lines);
    lf.displayCanny();
    lf.displayCyan();

    std::vector<point_t> oPixel;
    cv::Point pt1;
    cv::Point pt2;
    for ( int i = 0; i < lines.size(); i++)
      {
        pt1.x = lines[i][0];
        pt1.y = lines[i][1];
        pt2.x = lines[i][2];
        pt2.y = lines[i][3];
        cv::LineIterator it(rightImage, pt1, pt2, 8);
        for(int j = 0; j < it.count; j++, ++it){
            oPixel.push_back(point_t(it.pos().x,it.pos().y));
//            ROS_INFO("posx %d posY %d",int(it.pos().x),int(it.pos().y));

        }
//        ROS_INFO("siz OF oPixel %d",int(oPixel.size()));
      }


    PointCloud points;
    //cv::vector<cv::Vec4i> lines;
    // publish the point cloud containing 3d points
    if ( gets3dPoints(grabbedImage, triclops, disparityImage16, triclopsColorInput, oPixel, points) )
    {
        return EXIT_FAILURE;
    }
    else
    {
        points.header.frame_id="bumblebee2";
        // Problem with time format in PCL see: http://answers.ros.org/question/172241/pcl-and-rostime/
        //ros::Time time_st = ros::Time::now ();
        //points.header.stamp = time_st.toNSec()/1e3;
        //pcl_conversion::toPCL(ros::Time::now(), point_cloud_msg->header.stamp);
        pc2_pub.publish(points);

    }
    ros::spinOnce();
    loop_rate.sleep();
  }

}
