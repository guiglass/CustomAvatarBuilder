# Animation Prep Studio (Avatar Builder) V2.0.2

Contains features that help automate the process of converting .blend models into avatar assets compatible with [Animation Prep Studio (Lite)](https://drive.google.com/open?id=17MyFQ75dfBuaf5IL4ba-4BH8klWj6-5r "Animation Prep Studio Direct Download"). The builder tool can import .blend files which were created using blender [version 2.79b](https://download.blender.org/release/Blender2.79/ "Blender Downloads")
And have a compatible skeleton heirachy.

|   Skeletons   |   Supported   |
| :-------------| :-------------: |
|   Makehuman   |     Yes       |
|   CC3         |     Yes       |


After successful import there will be a new asset folder, then to make your item available in the game simply drag and drop the asset folder into the `VR_MocapAssets` folder located at:

`%USERPROFILE%\LocalLow\Animation Prep Studios\AnimationPrepStudio_Lite\VR_MocapAssets`

___
Youtube tutorial on how to create custom avatars from Makehuman/Reallusion -> Blender characters:
## Getting Started Reallusion:
[![Youtube Tutorial](https://img.youtube.com/vi/US4zInM82EM/0.jpg)](https://www.youtube.com/watch?v=US4zInM82EM)

## Getting Started Makehuman:
[![Youtube Tutorial](https://img.youtube.com/vi/gRIz8tc7ds8/0.jpg)](https://www.youtube.com/watch?v=gRIz8tc7ds8)

___
Below is documentation describing some of the steps required to create and add custom avatars.

![Test Image 4](https://raw.githubusercontent.com/guiglass/CustomAvatarBuilder/master/Documentation/builder.png)
* First be sure that the `Blender Application` field points to the valid blender.exe installed on your PC ([version 2.79b](https://download.blender.org/release/Blender2.79/ "Blender Downloads")).
* Then click the "Import Avatar Model" button to locate the .blend file containing the model you would like to import.

![Test Image 4](https://raw.githubusercontent.com/guiglass/CustomAvatarBuilder/master/Documentation/select.png)
* The automation should do most of the work creating the assetbundle.

![Test Image 4](https://raw.githubusercontent.com/guiglass/CustomAvatarBuilder/master/Documentation/asset.png)
___
Copy the entire folder:

`avatar$00000000-0000-0000-0000-000000000000$male_military`

And paste it into the folder at the path:

`%USERPROFILE%\AppData\LocalLow\Animation Prep Studios\AnimationPrepStudio_Lite`

___
### Installing

It is recommended to open this project using [Unity 2019.2.4f1](https://unity3d.com/unity/whats-new/2019.2.4 "Unity Engine Download").
You will also require [Blender 2.79b](https://download.blender.org/release/Blender2.79/ "Blender Downloads") to be installed.

Start Unity hub and navigate to this project, then select the `project` directory to open the project. Then load `Builder.unity`

![Test Image 4](https://raw.githubusercontent.com/guiglass/CustomAvatarBuilder/master/Documentation/scene.png)

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE - see the [LICENSE.md](LICENSE.md) file for details
