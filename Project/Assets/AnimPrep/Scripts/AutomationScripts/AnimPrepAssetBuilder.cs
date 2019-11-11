using System;
#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using System.Linq;
using System.IO;

[ExecuteInEditMode] public class AnimPrepAssetBuilder : EditorWindow 
{
	public static string BUILDER_VERSION = "2.2.1";
	
	[Header("References")]

	Texture2D logotex;

	public static string[] getCharacterTypesArray = System.Enum.GetNames(typeof(ArmatureLinker.CharacterType));
	
	//============================================
	[MenuItem("AnimPrep/Avatar Importer")]
	static void Init()
	{
		AnimPrepAssetBuilder window = (AnimPrepAssetBuilder)GetWindow(typeof(AnimPrepAssetBuilder));
		window.maxSize = new Vector2(300f, 335f);
		window.minSize = window.maxSize;

	}

	void OnEnable() {
		string[] tex = AssetDatabase.FindAssets("logotex", new[] {"Assets/AnimPrep"});
		if (tex.Length != 0) {
			byte[] fileData;
			fileData = File.ReadAllBytes (AssetDatabase.GUIDToAssetPath(tex[0]));
			logotex = new Texture2D (50, 50);
			logotex.LoadImage (fileData); //..this will auto-resize the texture dimensions.
		}

		if (!Directory.Exists (AnimPrepAssetPostprocessor.assetBundlesFolder)) {
			Directory.CreateDirectory (AnimPrepAssetPostprocessor.assetBundlesFolder);
		}

		CheckBlenderAppExists ();
	}

	void FixPlayerSettings()
	{
		PlayerSettings.colorSpace = ColorSpace.Linear;
		PlayerSettings.virtualRealitySupported = true;
		PlayerSettings.SetVirtualRealitySDKs(BuildTargetGroup.Standalone, new string[] { "OpenVR", } );
		PlayerSettings.stereoRenderingPath = StereoRenderingPath.SinglePass;
		PlayerSettings.companyName = "Animation Prep Studios";
		PlayerSettings.productName = "Avatar Builder";
		PlayerSettings.bundleVersion = BUILDER_VERSION;
	}
	
	string modelPathLast = "";
	const string blenderAppPathDefault = "C:\\Program Files\\Blender Foundation\\Blender\\blender.exe";
	string blenderAppPath = blenderAppPathDefault;
	bool blenderAppExists = false;


	int characterType = 0;

	
	
	
		

	[Serializable]
	public struct UserPrefs 
	{ //these refer to the JSON key/value pair which assiociates user settings with previously loaded avatars
		public float knees_rotation;
		public float feet_spacing;
	}

	[Serializable]
	public class Wrapper<T>
	{
		public MocapFileHeaderParameters Params;
		public T[] Indexes; //the file index information that links trackers/bones to the respective file line index
	}
	
	public static Wrapper<T> FromJson<T>(string json) {
		return UnityEngine.JsonUtility.FromJson<Wrapper<T>>(json);
	}
	
	protected static string ToJson<T>(T[] t)
	{
		Wrapper<T> wrapper = new Wrapper<T>();

		wrapper.Params = new MocapFileHeaderParameters()
		{
			//model = _armature.defaultModel,// VaptureTrackerLinker.Instance.mocapRig.retrackingFrames.fileParams.model,

			//fps = VaptureRecorder.fps, //the frames per second this animation was recorded at
		};

		wrapper.Indexes = t; //the main indexes for each tracker/bone
		return UnityEngine.JsonUtility.ToJson(wrapper);
	}

	[Serializable]
	public struct MocapFileHeaderParameters
	{
		//these refer to the JSON key/value pair which assiociates retrackers to their respective file line index position
		public string model; //the name of the asset bundle (aka model) this file is for
		public string path; //the directory folder name where the animation data is contained

	}




	void OnGUI()
    {

        var customButton = new GUIStyle("Button");
        GUIStyle customLabel;

        customLabel = new GUIStyle("Label");
        customLabel.fixedHeight = 50;

        GUI.Box(new Rect(0, 0, 50, 50), new GUIContent("", logotex), customLabel);

        Rect r = (Rect)EditorGUILayout.BeginVertical(customLabel);

        customLabel = new GUIStyle("Label");
        customLabel.alignment = TextAnchor.MiddleCenter;
        customLabel.fontSize = 14;
        customLabel.normal.textColor = Color.black;
        customLabel.fontStyle = FontStyle.Bold;

        GUILayout.Label("Custom Avatar Builder", customLabel);

        customLabel = new GUIStyle("Label");
        customLabel.alignment = TextAnchor.MiddleCenter;
        customLabel.fontSize = 11;
        customLabel.normal.textColor = new Color(0.5f, 0.5f, 0.5f);
        customLabel.fontStyle = FontStyle.Bold;

        GUILayout.Label(string.Format("Version: {0} (Lite)", BUILDER_VERSION/*Application.version*/), customLabel);

        EditorGUILayout.EndVertical();


        customLabel = new GUIStyle("Button");
        customLabel.alignment = TextAnchor.MiddleCenter;
        customLabel.fontSize = 10;
        customLabel.normal.textColor = new Color(0.2f, 0.2f, 0.2f);
        customLabel.fontStyle = FontStyle.Italic;
        customLabel.fixedWidth = 100;
        customLabel.normal.textColor = new Color(0.7f, 0.0f, 0.0f);

        //EditorGUILayout.LabelField("PATH WARNING!", customLabel, GUILayout.Width(100));

        if (!SystemInfo.operatingSystem.ToLower().Contains("windows 10"))
        {
            if (Application.dataPath.Length > 40) { 
                if (GUILayout.Button("PATH WARNING!", customLabel))
                {
                    EditorUtility.DisplayDialog("Warning",
                         string.Format(
                             "Your OS is: \"{0}\" which may experience issues with long paths." +
                             "\n\nIt would be wise to move this Builder project as close to \"C:\\\" as possible." +
                             "\n\nCurrent application datapath:\n{1}", 
                             SystemInfo.operatingSystem, Application.dataPath
                             ),
                         "Ok");

                    return;
                }
            }
        }
        
        customLabel = new GUIStyle ("Button");
		customLabel.alignment = TextAnchor.MiddleCenter;
		customLabel.fontSize = 14;
		customLabel.normal.textColor = new Color(0.0f,0.0f,1.0f);
		customLabel.fontStyle = FontStyle.Bold;


		EditorGUILayout.LabelField("Select the .blend file to process:");
		customLabel = new GUIStyle ("Button");
		customLabel.alignment = TextAnchor.MiddleCenter;
		customLabel.fontSize = 10;
		customLabel.normal.textColor = new Color(0.2f,0.2f,0.2f);
		customLabel.fontStyle = FontStyle.Italic;
		customLabel.fixedWidth = 100;


		customLabel = new GUIStyle ("Button");
		customLabel.alignment = TextAnchor.MiddleCenter;
		customLabel.fontSize = 14;
		customLabel.normal.textColor = new Color(0.0f,0.0f,1.0f);
		customLabel.fontStyle = FontStyle.Bold;
		
		if (GUILayout.Button(new GUIContent("Import Avatar Model", "Select .blend files containing valid models. Processes the model to generate a custom assetbundle compatible with AnimationPrepStudio runtime."), customLabel))
		{
			//WriteLineToFile(fs_retrack, ToJson(m_mocapRig, retrackerFileHeaderIndexs, fingerFileHeaderIndexs)); //Add the JSON header as the very first line
			//return;
			
			
			if (characterType == (int)ArmatureLinker.CharacterType.DEFAULT) {
				var enumName = System.Enum.GetName (typeof(ArmatureLinker.CharacterType), ArmatureLinker.CharacterType.DEFAULT);
				Debug.LogWarning(string.Format("You must specify a character type (\"{0}\" is not a valid selection)", enumName));
				EditorUtility.DisplayDialog("Error",
					string.Format("Character type: \"{0}\" is not a valid selection!\n\nPlease select a desired character type first.", enumName),
					"Ok");
				
				return;
			}

			if (!string.IsNullOrEmpty (blenderAppPath) && !File.Exists (blenderAppPath)) {
				EditorUtility.DisplayDialog("Blender Application Is Not Set",
					"Please browse for and select the installed Blender application. Must be version 2.79b.", "OK");
				return;
			}

			FixPlayerSettings();
			
            AssetDatabase.RemoveUnusedAssetBundleNames ();

			var modelPath = EditorUtility.OpenFilePanel(string.Format("Load {0} model", getCharacterTypesArray[characterType].ToLower() ), modelPathLast, "blend");

			if (!string.IsNullOrEmpty (modelPath)) {
				
				GameObject templateObject = null;

				switch ((ArmatureLinker.CharacterType)characterType) {
					case ArmatureLinker.CharacterType.DAZ3D_G3:
						templateObject = Resources.Load<GameObject> ("Pose_Daz3D_G3");
						break;
					case ArmatureLinker.CharacterType.DAZ3D_G2:
						templateObject = Resources.Load<GameObject> ("Pose_Daz3D_G2");
						break;
					case ArmatureLinker.CharacterType.MIXAMO:
						templateObject = Resources.Load<GameObject> ("Pose_Mixamo");
						break;
					case ArmatureLinker.CharacterType.CC3:
						templateObject = Resources.Load<GameObject> ("Pose_CC3");
						break;
					case ArmatureLinker.CharacterType.MAKEHUMAN:
					case ArmatureLinker.CharacterType.DEFAULT:
						templateObject = Resources.Load<GameObject> ("Pose_Makehuman");
						break;
					default:
						Debug.LogError ("Non-templateType detected - Filename must begin with a skeleton template type!");
						return;
				}

				var skeletonPath = Path.Combine(Path.GetDirectoryName(modelPath), "skeleton.csv");
				if (File.Exists(skeletonPath))
					File.Delete(skeletonPath);

				using (StreamWriter sw = File.AppendText(skeletonPath)) 
				{
					var children = templateObject.GetComponentsInChildren<Transform>();
					
					for (int i = 1; i < children.Length; i++)
					{
						var child = children[i].transform;
						sw.WriteLine(String.Format("{0},{1},{2},{3},{4},{5},{6},{7},{8}",
							child.name,
							child.parent.name,
							child.localPosition.x.ToString("F8"),
							child.localPosition.y.ToString("F8"),
							child.localPosition.z.ToString("F8"),
							child.localRotation.x.ToString("F8"),
							child.localRotation.y.ToString("F8"),
							child.localRotation.z.ToString("F8"),
							child.localRotation.w.ToString("F8")
						));
					}
				}
				
				modelPathLast = Path.GetDirectoryName(modelPath);
				if (Path.GetExtension (modelPath).Equals (".blend")) {
					if (!RunBatch (AnimPrepAssetPostprocessor.AssetBundleVariant, modelPath, blenderAppPath)) {
						EditorUtility.DisplayDialog("No AssetCreator.exe Tool",
							"Please ensure the AssetCreator.exe tool in located in the AnimPrep directory.", "OK");
						return;
					}

					var baseName = Path.GetFileNameWithoutExtension (modelPath);

					modelPath = Path.Combine (
						Path.Combine (
							Path.GetDirectoryName (modelPath), baseName.ToLower() + string.Format("_{0}", AnimPrepAssetPostprocessor.AssetBundleVariant.ToLower())
						),
						baseName + ".fbx"
					);
				}

				var uploadFolder = Path.GetDirectoryName (modelPath);

				//var userName = Path.GetFileName (SystemInfo.deviceName);

				var uploadFolderTop = new DirectoryInfo (uploadFolder).Name;

				var uploadName = System.Guid.NewGuid ().ToString ();// Path.GetFileName (uploadFolder);

				var processingPath = AnimPrepAssetPostprocessor.processingFolder;// Path.Combine(Application.dataPath, "MakeHumanModels");
				//processingPath = Path.Combine (processingPath, userName);
				processingPath = Path.Combine (processingPath, uploadName);

				System.IO.Directory.CreateDirectory (processingPath);


				DirectoryInfo dir = new DirectoryInfo (uploadFolder);
				FileInfo[] modelsInfo = dir.GetFiles ("*.fbx");

				if (modelsInfo.Length == 0) {
					Debug.LogError ("modelsInfo was empty. No .fbx file could be loaded.");
					return;
				}

				string uid = uploadName.Replace (AnimPrepAssetPostprocessor.templateSeperator.ToString(), "");// uploadFolderTop.Replace("$", "");


				//Copy all model files
				foreach (FileInfo f in modelsInfo) {
					var to = Path.Combine (
						processingPath,
						AnimPrepAssetPostprocessor.AssetBundleVariant + 
						AnimPrepAssetPostprocessor.templateSeperator +//"$"
						uid + 
						AnimPrepAssetPostprocessor.templateSeperator +//"$"
						f.Name
					);
					FileUtil.CopyFileOrDirectory (f.FullName, to);
				}

				//Copy all .json files
				FileInfo[] jsonInfo = dir.GetFiles ("*.json");
				foreach (FileInfo f in jsonInfo) {
					var to = Path.Combine (processingPath, f.Name);
					FileUtil.CopyFileOrDirectory (f.FullName, to);
				}

				//Copy all images files
				var textures_path = Path.Combine(uploadFolder, "textures");
				if (Directory.Exists(textures_path))
				{
					string[] extensions = new[] { ".png", ".jpg", ".tiff", ".bmp" };
				
					DirectoryInfo dir_images = new DirectoryInfo (textures_path);

					FileInfo[] texturesInfo =
						dir_images.GetFiles()
							.Where(f => extensions.Contains(f.Extension.ToLower()))
							.ToArray();

					foreach (FileInfo f in texturesInfo)
					{
						var to = Path.Combine(processingPath, f.Name);
						FileUtil.CopyFileOrDirectory(f.FullName, to);
					}
				}

				AnimPrepAssetPostprocessor.AssetBundleUserJson userPrefs = new AnimPrepAssetPostprocessor.AssetBundleUserJson () {
					created = System.DateTime.UtcNow,
					variantTag = getCharacterTypesArray[characterType],//use the index of the users selection to get then enum name from the chracter types
					//user = userName,
					//uploadFolder = uploadName,
					characterFolder = Path.GetDirectoryName(modelPath)
				};

				string json = JsonUtility.ToJson (userPrefs);
				var jsonPath = Path.Combine (AnimPrepAssetPostprocessor.assetBundlesFolder, uid + ".json");
				using (StreamWriter sr = new StreamWriter (jsonPath)) { // Create the file.
					sr.WriteLine (json);
				}


				AssetDatabase.Refresh ();

				BuildScript.BuildAssetBundles ();

				AssetDatabase.Refresh ();

				Debug.Log (string.Format("Created new {0} character!\nPress \"Append Prefabs To Scene\" button to see the newly created character.", getCharacterTypesArray[characterType].ToLower()));
			}
		}
		GUILayout.BeginHorizontal();


		
		
		characterType = EditorGUILayout.Popup(new GUIContent("Character Type:", "This must match the type of skeleton that the character model was created with."), characterType, getCharacterTypesArray, GUILayout.MinWidth (100)); 


		GUILayout.EndHorizontal();

		EditorGUILayout.Space();



		customLabel = new GUIStyle ("Button");
		customLabel.alignment = TextAnchor.MiddleCenter;
		customLabel.fontSize = 14;
		customLabel.normal.textColor = new Color(0.0f,0.5f,0.0f);
		customLabel.fontStyle = FontStyle.Bold;

		EditorGUILayout.LabelField("Save changes to assetbundles:");
		if (GUILayout.Button(new GUIContent("Re-Build Assetbundles", "After making any changes to avatars, this will update the changes to the local assetbundle files."), customLabel)) {

			FixPlayerSettings();
			
			var allPaths = AssetDatabase.GetAllAssetPaths ();
			foreach (var assetPath in allPaths) {
				if (assetPath.StartsWith(AnimPrepAssetPostprocessor.prefabsFolder)) {
					//ensure the prefab is enabled before saving as assetbundle

					string modelFileName = Path.GetFileNameWithoutExtension( assetPath );
					GameObject modelAsset = AssetDatabase.LoadAssetAtPath<GameObject> (assetPath); //LOADING AN ASSET
					if (modelAsset == null) {
						continue;
					}

					if (!modelAsset.activeSelf) {
						GameObject model = (GameObject)PrefabUtility.InstantiatePrefab(modelAsset);
						model.SetActive (true);
						PrefabUtility.SaveAsPrefabAsset (model, assetPath);
						GameObject.DestroyImmediate (model);
					}
				}
			}

			var allShaderKeywordParams = GameObject.FindObjectsOfType<RendererShaderParams> ();

			foreach (var shaderKeywordParams in allShaderKeywordParams) {
				shaderKeywordParams.StoreParams();
			}

			var allRootGos = UnityEngine.SceneManagement.SceneManager.GetActiveScene ().GetRootGameObjects ();
			foreach (var go in allRootGos) {
                
                //bool isPrefabInstance = PrefabUtility.GetPrefabParent(go) != null && PrefabUtility.GetPrefabObject(go.transform) != null;
                bool isPrefabInstance = PrefabUtility.GetCorrespondingObjectFromOriginalSource(go) != null && PrefabUtility.GetCorrespondingObjectFromOriginalSource(go.transform) != null;
				if (isPrefabInstance) {

					RendererShaderParams.StoreAllRenderers (go);

                    //PrefabUtility.ReplacePrefab(go, PrefabUtility.GetPrefabParent(go), ReplacePrefabOptions.ConnectToPrefab);
                    try
                    {
	                    PrefabUtility.SaveAsPrefabAssetAndConnect(go, PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(go), InteractionMode.AutomatedAction);
                    }
                    catch (Exception e)
                    {
	                    Debug.LogWarning(e.Message); //Ensure all assets will be processed. Ignores error: "Given path is not valid: 'Assets/Resources/armature_something.fbx"
                    }
				}
			}

			AssetDatabase.Refresh ();
			BuildScript.BuildAssetBundles ();
			AssetDatabase.Refresh ();

			ShowAssetBundlesExplorer ();

		}



		EditorGUILayout.Space();

		customLabel = new GUIStyle ("Button");
		customLabel.alignment = TextAnchor.MiddleCenter;
		customLabel.fontSize = 12;
		//customLabel.normal.textColor = new Color(0.0f,0.5f,0.0f);
		customLabel.fontStyle = FontStyle.Italic;

		EditorGUILayout.LabelField("Add processed models to scene:");


		if (GUILayout.Button(new GUIContent("Append Prefabs To Scene", "Places all prefabs into the current scene."), customLabel))	{

			//Vector3 offsetSpacing = Vector3.right * 1.5f;

			var info = new DirectoryInfo(AnimPrepAssetPostprocessor.prefabsFolder);
			var fileInfo = info.GetFiles("*.prefab", SearchOption.TopDirectoryOnly);

			for (int i = 0; i < fileInfo.Length; i++) {
				var file = fileInfo[i];

				if (Path.GetExtension (file.FullName).Equals (".meta")) {
					continue;
				}


				string fullPath = file.FullName.Replace(@"\","/");
				string assetPath = "Assets" + fullPath.Replace(Application.dataPath, "");


				bool alreadyInScene = false;
				var allRootGos = UnityEngine.SceneManagement.SceneManager.GetActiveScene ().GetRootGameObjects ();
				foreach (var go in allRootGos) {
					//bool isPrefabInstance = PrefabUtility.GetPrefabParent(go) != null && PrefabUtility.GetPrefabObject(go.transform) != null;
                    bool isPrefabInstance = PrefabUtility.GetCorrespondingObjectFromSource(go) != null && PrefabUtility.GetCorrespondingObjectFromSource(go.transform) != null;

                    if (isPrefabInstance) {
                        //Object parentObject = EditorUtility.GetPrefabParent(go);
                        UnityEngine.Object parentObject = PrefabUtility.GetCorrespondingObjectFromSource(go);
						string path = AssetDatabase.GetAssetPath(parentObject); 

						if (assetPath.Equals (path)) {
							alreadyInScene = true;
							break;
						}

					}
				}
				if (alreadyInScene) {
					continue;
				}



				UnityEngine.Object prefab = AssetDatabase.LoadMainAssetAtPath(assetPath);

				GameObject clone  = PrefabUtility.InstantiatePrefab(prefab as GameObject) as GameObject;

				//clone.transform.position = offsetSpacing * i;
			}
		}




		EditorGUILayout.Space();

		customLabel = new GUIStyle ("Button");
		customLabel.alignment = TextAnchor.MiddleCenter;
		customLabel.fontSize = 12;
		customLabel.normal.textColor = new Color(0.2f,0.2f,0.2f);
		customLabel.fontStyle = FontStyle.Italic;

		EditorGUILayout.LabelField("Show folder containing asset files:");
		GUILayout.BeginHorizontal();
		
		if (GUILayout.Button (new GUIContent("Assetbundles", "Opens the folder containing the newly created Assetbundle files."), customLabel)) {
			ShowAssetBundlesExplorer ();
		}

		customLabel.normal.textColor = new Color(1.0f,0.2f,0.2f);
		if (GUILayout.Button (new GUIContent("VR_MocapAssets", "This is the destination folder where you should copy Assetbundles to for them to be included in AnimationPrepStudio runtime."), customLabel)) {
			ShowMocapAssetsExplorer ();
		}
		GUILayout.EndHorizontal();

		EditorGUILayout.Space();



		GUILayout.BeginHorizontal();
		EditorGUILayout.LabelField("Blender Application (v2.79b):", GUILayout.MinWidth (0));

		customLabel = new GUIStyle ("Label");
		customLabel.alignment = TextAnchor.MiddleCenter;
		customLabel.fontStyle = FontStyle.BoldAndItalic;

		if (blenderAppExists) {
			customLabel.normal.textColor = new Color (0.0f, 0.5f, 0.0f);
			EditorGUILayout.LabelField ("File Exists", customLabel, GUILayout.Width (100));
		} else {
			customLabel.normal.textColor = new Color (0.5f, 0.0f, 0.0f);
			EditorGUILayout.LabelField ("File Missing!", customLabel, GUILayout.Width (100));

			customButton = new GUIStyle ("Button");
			customButton.alignment = TextAnchor.MiddleCenter;
			customButton.fontSize = 10;
			customButton.normal.textColor = new Color(0.2f,0.2f,0.2f);
			customButton.fontStyle = FontStyle.Italic;
			customButton.fixedWidth = 100;
			if (GUILayout.Button ("Default", customButton)) {
				blenderAppPath = blenderAppPathDefault;
			}

		}
		GUILayout.EndHorizontal();

		GUILayout.BeginHorizontal();

		customLabel = new GUIStyle ("Button");
		customLabel.alignment = TextAnchor.MiddleCenter;
		customLabel.fontSize = 10;
		customLabel.normal.textColor = new Color(0.2f,0.2f,0.2f);
		customLabel.fontStyle = FontStyle.Italic;
		customLabel.fixedWidth = 100;

		blenderAppPath = GUILayout.TextField(blenderAppPath, GUILayout.MinWidth (0));
		if (GUILayout.Button (new GUIContent("Browse", "Select a valid Blender v2.79b installation path by locating and selecting the \"blender.exe\" runtime application file."), customLabel)) {
			string modelPath = EditorUtility.OpenFilePanel("Blender Application (v2.79b)", Path.GetDirectoryName(blenderAppPath), "exe");
			if (!string.IsNullOrEmpty (modelPath)) {
				blenderAppPath = modelPath;
			}
		}
		GUILayout.EndHorizontal();
        EditorGUILayout.Space();

        customLabel = new GUIStyle("Label");
        customLabel.alignment = TextAnchor.MiddleCenter;
        customLabel.fontStyle = FontStyle.Italic;
        GUILayout.Label(string.Format("{0} - {1}", Application.unityVersion, SystemInfo.operatingSystem), customLabel);

        if (GUI.changed)
		{

			CheckBlenderAppExists ();
		}

		this.Repaint();
	}

	void CheckBlenderAppExists() {
		blenderAppExists = !string.IsNullOrEmpty (blenderAppPath) && File.Exists (blenderAppPath);
	}


	public static void ShowAssetBundlesExplorer()
	{
		//ShowExplorer ( Application.dataPath + Path.Combine("/../", AnimPrepAssetPostprocessor.assetBundlesFolder));
        ShowExplorer(Application.dataPath + Path.Combine(string.Format("{0}..{0}", Path.DirectorySeparatorChar), AnimPrepAssetPostprocessor.assetBundlesFolder));
    }
	
	public static void ShowMocapAssetsExplorer()
	{
		ShowExplorer(
			Environment.ExpandEnvironmentVariables(
				string.Format("%userprofile%{0}appdata{0}localLow{0}Animation Prep Studios{0}AnimationPrepStudio_Lite{0}VR_MocapAssets{0}", Path.DirectorySeparatorChar)
			));
	}
	
	public static void ShowExplorer(string itemPath)
	{
		Debug.Log(itemPath);
		//itemPath = itemPath.Replace (@"/", @"\");//  @"\");   // explorer doesn't like front slashes
		System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo() {
			FileName = itemPath,
			UseShellExecute = true,
			Verb = "open"
		});
	}

	public static bool RunBatch (string assetType, string modelPath, string blenderPath) {
		var path = "Assets\\AnimPrep\\AssetCreator.exe";
		if (!File.Exists (path)) {
			Debug.LogError ("The AssetCreator.exe tool was missing");
			return false;
		}

		try {
			System.Diagnostics.Process myProcess = new System.Diagnostics.Process();
			myProcess.StartInfo.WindowStyle = System.Diagnostics.ProcessWindowStyle.Hidden;
			myProcess.StartInfo.CreateNoWindow = true;
			myProcess.StartInfo.UseShellExecute = false;
			myProcess.StartInfo.FileName = "C:\\Windows\\system32\\cmd.exe";
			path = string.Format("{0} {1} \"{2}\" \"{3}\"", path, assetType, modelPath, blenderPath);
			myProcess.StartInfo.Arguments = "/c" + path;
			myProcess.EnableRaisingEvents = true;
			myProcess.Start();
			myProcess.WaitForExit();
			int ExitCode = myProcess.ExitCode;
			return true;
		} catch (System.Exception e){
			Debug.Log(e);
		}
		return false;
	}

}


public class BuildScript
{
	public static void BuildAssetBundles ()
	{
		//TODO Assertion failed: AssetBundle index doesn't exist in the asset database.
		BuildPipeline.BuildAssetBundles(AnimPrepAssetPostprocessor.assetBundlesFolder, BuildAssetBundleOptions.None, BuildTarget.StandaloneWindows);
	}

	public static void BuildAssetBundles (AssetBundleBuild[] assetBundleBuilds)
	{
		BuildPipeline.BuildAssetBundles(AnimPrepAssetPostprocessor.assetBundlesFolder, assetBundleBuilds, BuildAssetBundleOptions.None, BuildTarget.StandaloneWindows);
	}
}


#endif