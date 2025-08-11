import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LoadComposableNodes, Node
from launch_ros.descriptions import ComposableNode


def launch_setup(context, *args, **kwargs):
    name = LaunchConfiguration("name").perform(context)
    depthai_prefix = get_package_share_directory("depthai_ros_driver")

    params_file = LaunchConfiguration("params_file")
    parameters = [
        {
            "frame_id": name,
            "subscribe_rgb": True,
            "subscribe_depth": True,
            "subscribe_odom_info": True,
            "subscribe_odom": True, # /odom topic-ийг SLAM node-д сонсохыг болиулав
            "approx_sync": True,
            "approx_sync_max_interval": 0.05, 
            "topic_queue_size": 30,
			"sync_queue_size": 30,
            "Rtabmap/DetectionRate": "1",
            
           # "Odom/Stereo/Swap": True,
            
          #  "Mem/STMSize": "20",           # Богино хугацааны санах ойг багасгах
            
					  # --- Odometry хурдны тохиргоо ---
		#	"Odom/Strategy": "0",          # 0=Frame-to-Frame, 1=Frame-to-Map. 0 нь ихэвчлэн хурдан.
		#	"OdomF2M/MaxSize": "1000",     # Frame-to-Map ашиглаж байвал local map-ийн хэмжээг хязгаарлах
		#	"Vis/MaxFeatures": "1500",      # Feature-ийн тоог багасгах (1000 -> 600)
		#	"GFTT/MaxCorners": "1500",      # Дээрхтэй ижил
		
			"Vis/MinInliers": "20",  # Анхдагч утга нь 10 байдаг. 20-30 болгосноор буруу таамаглалыг шүүнэ.
			"Vis/FeatureType": "8",      # 0=SURF, 1=SIFT, ..., 7=GFTT (default), 8=ORB
		
        
            "Grid/CellSize": "0.03",
			"Grid/MinDepth": "0.2",
			"Grid/MaxDepth": "3.5",
			"Cloud/Decimation": "2.0",
			"Cloud/VoxelSize": "0.05",
			"Grid/MaxGroundHeight": "-0.25",        # Шалнаас 10см дээш л саад гэж үз
			"Grid/MaxObstacleHeight": "1.5",      # 1.5м-ээс дээшээ саад биш
			"Grid/ClusterRadius": "0.1",          # 10см доторхи жижиг object-ууд нэгтгэнэ
			"Grid/Global/MinClusterSize": "20",   # 10-аас доош цэгтэй кластерыг арилгана
			"Grid/RayTracing": "true",            # Ханын ирмэгийг сайн ялгана
			"Grid/NormalsSegmentation": "true",   # Plane segmentation (depth-ээр)
			
			
			"Reg/Force3DoF": "true",      # IMU-аас ирэх эргэлтийн мэдээлэлд илүү итгэнэ
			"subscribe_imu": True,      # /imu topic-ийг сонсоно
            "Odom/ResetCountdown": "0",
        }
    ]

    stereo_remappings = [
        ('left/image_rect', name + '/left/image_rect'),
        ('right/image_rect', name + '/right/image_rect'),
        ('left/camera_info', name + '/left/camera_info'),
        ('right/camera_info', name + '/right/camera_info'),
    ]
    
    slam_remappings = [
		('rgb/image', '/oak/left/image_rect'),       # Газрын зургийн өнгөнд зүүн талын зургийг ашиглана
		('rgb/camera_info', '/oak/left/camera_info'), # Түүний мэдээллийг ашиглана
		('depth/image', '/oak/stereo/image_raw'),          # Гүний мэдээлэлд depth image-г ашиглана
	]
    
    rgbd_remappings = [
        ('rgb/image', name + '/left/image_rect'),
        ('rgb/camera_info', name + '/left/camera_info'),
        ('depth/image', name + '/stereo/image_raw'),
        ('imu', '/imu')
    ]

    # Камер эхлүүлэх
    camera_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(depthai_prefix, "launch", "camera.launch.py")
        ),
        launch_arguments={
            "name": name,
            "params_file": params_file,
            "rectify_rgb": "true", # RTAB-Map-д rectified image хэрэгтэй
            "pointcloud.enable": "true", # Nav2-ийн costmap-д зориулж point cloud-г идэвхжүүлнэ
        }.items(),
    )

    # RTAB-Map болон rgbd_odometry-г delay-тайгаар эхлүүлэх
    rtabmap_launch = TimerAction(
        period=3.0,  # Хүсвэл 5 болгож болно
        actions=[
            LoadComposableNodes(
                target_container=name + "_container",
                composable_node_descriptions=[
                    ComposableNode(
                        package="rtabmap_odom",
                        plugin="rtabmap_odom::RGBDOdometry",
                        name="rgbd_odometry",
                        parameters=parameters,
                        remappings=rgbd_remappings,
                    ),
                ],
            ),
            LoadComposableNodes(
                target_container=name + "_container",
                composable_node_descriptions=[
                    ComposableNode(
                        package="rtabmap_slam",
                        plugin="rtabmap_slam::CoreWrapper",
                        name="rtabmap",
                        parameters=parameters,
                        remappings=rgbd_remappings,
                    ),
                ],
            ),
            # Хэрэв rtabmap_viz хэрэгтэй бол энд нэмнэ
            # Node(
            #     package="rtabmap_viz",
            #     executable="rtabmap_viz",
            #     output="screen",
            #     parameters=parameters,
            #     remappings=remappings,
            # ),
        ],
    )
    
    static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='oak_imu_static_tf',
        arguments=['0', '0', '0', '0', '0', '0', 'oak', 'imu'],
        output='screen'
    )

    return [
        camera_launch,
        rtabmap_launch,
        static_tf,
    ]


def generate_launch_description():
    depthai_prefix = get_package_share_directory("depthai_ros_driver")
    declared_arguments = [
        DeclareLaunchArgument("name", default_value="oak"),
        DeclareLaunchArgument(
            "params_file",
            default_value=os.path.join(depthai_prefix, "config", "rgbd.yaml"),
        ),
    ]

    return LaunchDescription(
        declared_arguments + [OpaqueFunction(function=launch_setup)]
    )
