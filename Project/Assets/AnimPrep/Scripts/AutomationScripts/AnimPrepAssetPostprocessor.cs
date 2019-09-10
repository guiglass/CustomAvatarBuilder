using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;
using System.IO;
using System.Linq;
using System.IO.Compression;

using System.Reflection;
using System.Text;
using System.Threading;

#if UNITY_EDITOR
using UnityEditor;
public class AnimPrepAssetPostprocessor : AssetPostprocessor {
	/// <summary>
	/// Helper class for automatically setting the bone mappings for default humanoid skeletons. Note that all imports must 
	/// be prepended with "MakeHuman_" (case insensitive). eg makehuman_mychar.fbx
	/// 
	/// https://forum.unity.com/threads/modelimporter-how-to-import-as-humanoid.487727/
	/// 
	/// Also it is important to note that two final manual steps are required. After the character has been imported as humanoid, 
	/// you must alos go into config and press enforce t-pose and apply. otherwise warnaing messages will be displayed.
	/// 
	/// Note that if animatios will not play properly, or at all, then it may be because the limits are not set correctly (or are zeros).
	/// If this is the case, then you must (uncomment the "Uncomment Me" section and) use debugging to determine the limit values for this template.
	/// You may goto muscles dropdown menu and press on "reset", to print what the limits should be.
	/// </summary>



	[System.Serializable]
	public struct BlenderColorJson
	{
		public float r;
		public float g;
		public float b;
	}

	[System.Serializable]
	public struct TextureSlotsJson
	{
		public string filename;

		public bool use_map_color_diffuse;
		public bool use_map_specular;
		public float specular_factor;

		public bool use_map_normal;
		public float normal_factor;

		public bool use_map_emit;
		public float emit_factor;
	}
	[System.Serializable]
	public struct MaterialsJson
	{
		public string key;
		public string texture;
		public float alpha;
		public bool use_transparency;

		public float diffuse_intensity;
		public float specular_intensity;
		public float specular_hardness;
		public BlenderColorJson specular_color;

		public TextureSlotsJson[] texture_slots;
	}

	[System.Serializable]
	public class BlenderJsonObject
	{
		public List<MaterialsJson> materials;
		public List<ArmatureLinker.ExpessionsJson> expressions;
	}

	[System.Serializable]
	public struct AssetBundleUserJson
	{
		public DateTime created;		
		public string variantTag;
		//public string user;
		//public string uploadFolder; //the folder that this script has copied the character fils and texture to for processing
		public string characterFolder; //the folder where the .fbx and .blend files were originally placed when the user created them
	}


	private const string reimportTag = "REIMPORT";
	private const string processedTag = "PROCESSED";
	private const string mappedTag = "MAPPED";

	public const string AssetBundleVariant = "avatar"; //the name given to the files created by AnimPrep.exe

	public const string MakehumanAssetVariantTag = "MAKEHUMAN";
	public const string ReallusionAssetVariantTag = "REALLUSION";

    //public static string assetBundlesFolder = "Assets/AssetBundles";
    public static string assetBundlesFolder { get { return String.Format("Assets{0}AssetBundles", Path.DirectorySeparatorChar); } }

    //public static string processingFolder = "Assets/AnimPrep_Processing";
    public static string processingFolder { get { return String.Format("Assets{0}AnimPrep_Processing", Path.DirectorySeparatorChar); } }
    
    //public const string prefabsFolder = "Assets/AnimPrep_Prefabs/"; //the folder to store prefabs
    public static string prefabsFolder { get { return String.Format("Assets{0}AnimPrep_Prefabs", Path.DirectorySeparatorChar); } }

    public static char templateSeperator = '$';

	private static string[] templates = new string[] {AssetBundleVariant};


	private string CheckIsTemplate(string[] _templates) {
		foreach (string template in _templates) {
			var cleanedAssetPath = Path.GetFileNameWithoutExtension (assetPath.ToLower ());
			if (cleanedAssetPath.StartsWith (template.ToLower() + templateSeperator)) {
				return template;
			}
		}
		return "";
	}


	void OnPreprocessAnimation()
	{
		ModelImporter importer = assetImporter as ModelImporter;

		if (!importer.userData.Contains(reimportTag)) {//do not affect any other .fbx except for actual template avatars (aka re-imported models)
			return;
		}

		importer.clipAnimations = importer.defaultClipAnimations;
	}


	private void OnPreprocessModel() {
        //Load in the preconfigured avatar from the resources folder
        assetPath = assetPath.Replace('/', Path.DirectorySeparatorChar); //fix the path so that it uses the correct seperator for this system


        string templateType = CheckIsTemplate (templates);
		if (!String.IsNullOrEmpty(templateType)) {		
			
			var importer = (ModelImporter) assetImporter;

			/*
			var animations = importer.clipAnimations;
			Debug.Log ("ANIMATION importer ????");
			foreach (var animation in animations) {
				Debug.Log ("ANIMATION NAME " + animation.name + " " + animation.takeName);

				if (animation.name.Contains ("RestPose")) {
					Debug.Log ("FOUND A REST POSE!!!! ");


					var curves = animation.curves;

					foreach (var curve in curves) {
						Debug.Log (curve.name + " " + curve.curve.length);

						//importer.defaultClipAnimations

					}

				}

			}
			*/

			if (Path.GetExtension (assetPath) != ".fbx") {
				importer.animationType = ModelImporterAnimationType.None;
				return;
			}

			if (!importer.userData.Contains (reimportTag)) {
				if (importer.animationType != ModelImporterAnimationType.Human) { //if the type is ever changed from human, then invalidate userdata so it will force everythin to be re-run
					importer.userData = ""; //reset the user data
				}
			}


			if (importer.userData.Contains(mappedTag)) {//Must re-import or else humandescription bones might still worng (as well as other things)
				return;
			}


			/*switch (templateType) {
			case ReallusionAssetVariantTag:
				importer.userData = importer.userData + " " + ReallusionAssetVariantTag;
				break;
			case AssetBundleVariant:
			case MakehumanAssetVariantTag:
				importer.userData = importer.userData + " " + MakehumanAssetVariantTag;
				break;
			default:
				Debug.LogError ("Non-templateType detected - Filename must begine with a skeleton template type!");
				return;
			}*/

			importer.isReadable = true;

			importer.importAnimation = true;
			importer.importMaterials = true;
			importer.importCameras = false;
			importer.importLights = false;

			importer.materialLocation = ModelImporterMaterialLocation.External;

			//Blender's normals are wrong when imported into unity causing artifacts in whole body when using blendshapes, use calculate to force unity to make the normals correct.
			importer.importNormals = ModelImporterNormals.Calculate; 
			importer.importBlendShapeNormals = ModelImporterNormals.Calculate;

			if (importer.userData.Contains (reimportTag)) {
				importer.animationType = ModelImporterAnimationType.Human;
			} else {
				importer.animationType = ModelImporterAnimationType.Generic;
			}

		}
	}



	//This is a Reallusion default facerig (and weights are for vocalizer expressions)
	public ArmatureLinker.BlendShapeParams[] faceRenderersParams_Reallusion /*= new BlendShapeParams[]{};*/ = new ArmatureLinker.BlendShapeParams[] {
		new ArmatureLinker.BlendShapeParams() {shapeName = "Brow_Drop_L", shapeWeight = 2.5f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "Brow_Drop_R", shapeWeight = 2.5f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "Eye_Squint_L", shapeWeight = 2.0f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "Eye_Squint_R", shapeWeight = 2.0f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "Cheek_Blow_L", shapeWeight = 0.8f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "Cheek_Blow_R", shapeWeight = 0.8f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "Cheek_Raise_L", shapeWeight = 1.0f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "Cheek_Raise_R", shapeWeight = 1.0f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "Mouth_Smile_L",  shapeWeight = 5.0f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "Mouth_Smile_R", shapeWeight = 5.0f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "Lip_Open", shapeWeight = 7.5f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "Mouth_Top_Lip_Up", shapeWeight = 5.0f},
	};


	//This is a MakeHuman default facerig (and weights are for vocalizer expressions)
	public ArmatureLinker.BlendShapeParams[] faceRenderersParams_MakeHuman /*= new BlendShapeParams[]{};*/ = new ArmatureLinker.BlendShapeParams[] {
		new ArmatureLinker.BlendShapeParams() {shapeName = "brow_mid_down_left",    shapeWeight = 2.5f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "brow_mid_down_right",   shapeWeight = 2.5f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "cheek_squint_left",     shapeWeight = 2.0f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "cheek_squint_right",    shapeWeight = 2.0f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "cheek_balloon_left",    shapeWeight = 0.8f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "cheek_balloon_right",   shapeWeight = 0.8f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "cheek_up_left",         shapeWeight = 1.0f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "cheek_up_right",        shapeWeight = 1.0f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "mouth_corner_in_left",  shapeWeight = 1.0f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "mouth_corner_in_right", shapeWeight = 1.0f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "mouth_corner_up_left",  shapeWeight = 5.0f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "mouth_corner_up_right", shapeWeight = 5.0f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "mouth_wide_left",       shapeWeight = 15.0f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "mouth_wide_right",      shapeWeight = 15.0f},

		new ArmatureLinker.BlendShapeParams() {shapeName = "lips_part",             shapeWeight = 7.5f},
		new ArmatureLinker.BlendShapeParams() {shapeName = "lips_upper_in",         shapeWeight = 5.0f},
	};


	static Func<string, string, HumanBone> Bone = (humanName, boneName) => new HumanBone() {humanName = humanName, boneName = boneName};
	static Func<string, Vector3, Quaternion, Vector3, SkeletonBone> Skel = (name, position, rotation, scale) => new SkeletonBone() {name = name, position = position, rotation = rotation, scale = scale};

	static string[] makehumanTemplateOverrideBoneNames = new string[] {
		//"jaw",          
		//"eye.L",        
		//"eye.R",        

		//"neck02",       
		//"neck01",       
		//"spine01",      
		//"spine02",      
		//"spine04",      
		//"root",         

		"finger2-3.R",  
		"finger2-2.R",  
		"finger2-1.R",  
		"finger3-3.R",  
		"finger3-2.R",  
		"finger3-1.R",  
		"finger4-3.R",  
		"finger4-2.R",  
		"finger4-1.R",  
		"finger5-3.R",  
		"finger5-2.R",  
		"finger5-1.R",  
		"finger1-3.R",  
		"finger1-2.R",  
		"finger1-1.R",  

		//"toe1-1.R",     
		//"foot.R",       
		"wrist.R",      
		//
		"lowerarm01.R", 
		//"lowerleg01.R", 
		"shoulder01.R", 
		"upperarm01.R", 
		//"upperleg01.R", 

		"finger2-3.L",  
		"finger2-2.L",  
		"finger2-1.L",  
		"finger3-3.L",  
		"finger3-2.L",  
		"finger3-1.L",  
		"finger4-3.L",  
		"finger4-2.L",  
		"finger4-1.L",  
		"finger5-3.L",  
		"finger5-2.L",  
		"finger5-1.L",  
		"finger1-3.L",  
		"finger1-2.L",  
		"finger1-1.L",  

		//"toe1-1.L",     
		//"foot.L",       
		"wrist.L",      

		"lowerarm01.L", 
		//"lowerleg01.L", 
		"shoulder01.L", 
		"upperarm01.L", 
		//"upperleg01.L", 
	};

	static string[] reallusionTemplateOverrideBoneNames = new string[] { 

		"CC_Base_R_Index1",  
		"CC_Base_R_Index2",  
		"CC_Base_R_Index3",  
		"CC_Base_R_Mid1",  
		"CC_Base_R_Mid2",  
		"CC_Base_R_Mid3",  
		"CC_Base_R_Ring1",  
		"CC_Base_R_Ring2",  
		"CC_Base_R_Ring3",  
		"CC_Base_R_Pinky1",  
		"CC_Base_R_Pinky2",  
		"CC_Base_R_Pinky3",  
		"CC_Base_R_Thumb1",  
		"CC_Base_R_Thumb2",  
		"CC_Base_R_Thumb3",  
    
		"CC_Base_R_Hand",      

		"CC_Base_R_Forearm", 

		"CC_Base_R_Clavicle", 
		"CC_Base_R_Upperarm", 


		"CC_Base_L_Index1",  
		"CC_Base_L_Index2",  
		"CC_Base_L_Index3",  
		"CC_Base_L_Mid1",  
		"CC_Base_L_Mid2",  
		"CC_Base_L_Mid3",  
		"CC_Base_L_Ring1",  
		"CC_Base_L_Ring2",  
		"CC_Base_L_Ring3",  
		"CC_Base_L_Pinky1",  
		"CC_Base_L_Pinky2",  
		"CC_Base_L_Pinky3",  
		"CC_Base_L_Thumb1",  
		"CC_Base_L_Thumb2",  
		"CC_Base_L_Thumb3",  
		     
		"CC_Base_L_Hand",      

		"CC_Base_L_Forearm", 

		"CC_Base_L_Clavicle", 
		"CC_Base_L_Upperarm", 
	};

	static void FixCharacterBones(GameObject modelAsset, SkeletonBone[] skelBones, HumanDescription humanDescription, string[] templateOverrideBoneNames ) {
		
		skelBones [0] = Skel (humanDescription.skeleton[0].name, humanDescription.skeleton[0].position, humanDescription.skeleton[0].rotation, humanDescription.skeleton[0].scale);

		for (int i = 1; i < skelBones.Count (); i++) { //for each bone in the template avatar skeleton
			
			var real = (from m in humanDescription.skeleton //find any bone in the real aramture that also exists in the tempate avatar skeleton
				where m.name.Equals (skelBones [i].name)
				select m).FirstOrDefault();

			if (templateOverrideBoneNames.Contains(skelBones [i].name)) { //if this bone should be overridden by the template transform offsets
				skelBones [i] = Skel (skelBones [i].name, real.position, skelBones [i].rotation, skelBones [i].scale);

			} else { //Use original transforms and not be changed
				skelBones [i] = Skel (skelBones [i].name, real.position, real.rotation, real.scale);
			}				

		}
	}

	public static void ApplyTemplateSkeleton(ModelImporter modelImporter, GameObject modelAsset, ArmatureLinker.CharacterType characterType)
	{
		GameObject fbxObject = null;
		string[] templateOverrideBoneNames = null;

		switch (characterType) {
		case ArmatureLinker.CharacterType.REALLUSION:
			fbxObject = Resources.Load<GameObject> ("ReallusionPose");
			templateOverrideBoneNames = reallusionTemplateOverrideBoneNames;
			break;
		case ArmatureLinker.CharacterType.MAKEHUMAN:
		case ArmatureLinker.CharacterType.DEFAULT:
			fbxObject = Resources.Load<GameObject> ("MakehumanPose");
			templateOverrideBoneNames = makehumanTemplateOverrideBoneNames;
			break;
		default:
			Debug.LogError ("Non-templateType detected - Filename must begine with a skeleton template type!");
			return;
		}

		/*bool isRellusion = true;
		if (isRellusion) {
			fbxObject = Resources.Load<GameObject> ("ReallusionPose");
		} else {
			fbxObject = Resources.Load<GameObject> ("MakehumanPose");
		}*/

		if (fbxObject == null) {
			Debug.LogError ("Error: The TemplateAvatar was not found in the Resources folder. Can not create the HumanDescription or set the T-Pose for this character.");
			return;
		}

		var templateAvatar = fbxObject.GetComponent<Animator>().avatar;
		var templateSkel = templateAvatar.humanDescription.skeleton;
		List<SkeletonBone> skelBones = new List<SkeletonBone> (templateSkel);

		FixCharacterBones (modelAsset, templateSkel /*skelBones*/, modelImporter.humanDescription, templateOverrideBoneNames);

		var hd = templateAvatar.humanDescription; //a new human description with the mutable arrays (Using the template HumanBones as bone connection defs)
		hd.skeleton = templateSkel;// skelBones.ToArray (); //apply the custom skeleton

		modelImporter.humanDescription = hd;
	}

	static Texture GetFileByKeywords(string path, string[] keywords) {
		var folder = Path.GetDirectoryName (path);
		var filename = Path.GetFileNameWithoutExtension (path);

		//Debug.Log("Searching path " + folder);
		DirectoryInfo dir = new DirectoryInfo(folder);
		FileInfo[] texturesInfo = dir.GetFiles ();

		foreach (FileInfo f in texturesInfo) {
			if (!f.Name.Contains (filename) || f.Name.Contains (".meta")) {
				continue;
			}
			foreach (string keyword in keywords) {
				if (f.Name.Contains (keyword)) {
					var tex = AssetDatabase.LoadAssetAtPath (Path.Combine(folder,f.Name), typeof(Texture)) as Texture;
					//Debug.Log ("TEX " + tex);
					return tex;
				}
			}
		}
		return null;
	}


	void OnPostprocessModel(GameObject model) {

		var importer = (ModelImporter) assetImporter;

		//Check/Add flags to indicate finished
		if (importer.userData.Contains(processedTag))
			return;
		
		importer.userData = importer.userData + " " + processedTag;
	}

	static void FitFootCollider(Transform puppetFoot, Transform armatureFoot) {//rotate and scale the box colliders added by MakePuppet so to fit better (may be makehuman specific)

		var footLCollider = puppetFoot.GetComponent<BoxCollider> ();

		puppetFoot.rotation = Quaternion.identity;
		puppetFoot.Rotate (Vector3.right * 90f);

		while (armatureFoot.childCount > 0) {
			armatureFoot = armatureFoot.GetChild (0);
		}

		var toeDis = (armatureFoot.position - puppetFoot.position).z;

		var yWorldCenter = (toeDis / 2f) - (toeDis * 0.25f / 2f);
		var yWorldSize = toeDis + (toeDis * 0.25f);

		var zWorldSize = puppetFoot.position.y;
		var zWorldCenter = puppetFoot.position.y / 2f;

		footLCollider.center = new Vector3 (0, yWorldCenter, zWorldCenter);
		footLCollider.size = new Vector3 (toeDis / 2f, yWorldSize, zWorldSize);
	}

	static Dictionary<string, MaterialsJson> BuildMaterialsDict(List<MaterialsJson> materialsList) {
		Dictionary<string, MaterialsJson> dict = new Dictionary<string, MaterialsJson> ();


		foreach (var material in materialsList) {
			var key = Path.GetFileNameWithoutExtension( String.IsNullOrEmpty (material.texture) ? material.key : material.texture );//unity is weird as it likes to create materials with the texture name when a texture was used

			if (dict.ContainsKey(key)) {
				if (dict [key].use_transparency) { //check if anythinig has already set the alpha to true, if so it takes presidence over any other
					continue; //some object has already set it to use alpha, thus it should remain as such even if another object says it is not transpareant#some object has already set it to use alpha, thus it should remain as such even if another object says it is not transpareant
				}
			}

			dict [key] = material;
		}

		return dict;
	}

	//TEXTURES
	void OnPreprocessTexture()
	{
        assetPath = assetPath.Replace('/', Path.DirectorySeparatorChar); //fix the path so that it uses the correct seperator for this system

        if (!assetPath.StartsWith (processingFolder)) { //only check textures in the upload processing folder
			Debug.LogWarning(assetPath + " TEXTURE DOES NOT BELONG TO: " + processingFolder);
			return;
		}

		var importer = (TextureImporter) assetImporter;

		string assetFolder = Path.GetDirectoryName (importer.assetPath);
		string blenderJsonPath = Path.Combine (assetFolder, "blender.json");
         
        if (File.Exists (blenderJsonPath)) { //check if the blender materials json exists
            
			BlenderJsonObject blenderJsonArray = JsonUtility.FromJson<BlenderJsonObject> (
				File.ReadAllText (blenderJsonPath)
			);

			Dictionary<string, MaterialsJson> materialsJson = BuildMaterialsDict (blenderJsonArray.materials);
			//Dictionary<string, MaterialsJson> materialsJson = blenderJsonArray.materials.ToDictionary (x => x.key, x => x);//convert KeyValuePair to Dictionary - https://stackoverflow.com/a/18955562/3961748

			var fileName = Path.GetFileName (assetPath);
			//check all materials and textures from blender to find this texure and check if it was set as a normal map in blender
			foreach (var blenderMaterial in blenderJsonArray.materials) {
				foreach (var slot in blenderMaterial.texture_slots) {
					if (slot.filename.Equals (fileName)) {
						if (slot.use_map_normal) {
							importer.textureType = TextureImporterType.NormalMap;
							return;
						}
					}
				}
			}

		} else {
			//fallback incase no blender material Json was available (or the user uploaded only the .fbx file)
			var fileName = Path.GetFileName (assetPath).ToLower ();
			if (fileName.Contains ("_normal") || fileName.Contains ("_nrm") || fileName.Contains ("_bumpmap") || fileName.Contains ("_norm") || fileName.Contains ("_height")) {
				TextureImporter textureImporter = (TextureImporter)assetImporter;
				textureImporter.textureType = TextureImporterType.NormalMap;
				return;
			}
		}

		importer.textureType = TextureImporterType.Default; //set the default, if nothing was changed
	}
		

	public struct MakehumanRenderer {
		public Renderer renderer;
		public MakehumanMeshBoneType type;
	}


	public enum MakehumanMeshBoneType {
		none,
		eyeballs,
		eyelashes,
		eyebrows,
		teeth,
		tongue		
	}





	public static GameObject CreateRestPoseRig(GameObject baseRig, string assetPath) {

		var animator = baseRig.transform.root.GetComponentInChildren<Animator> ();

		animator.enabled = false;

		//assetPath = "Assets/AnimPrep_Processing/224342ca-a8b2-4a9a-8e14-8206253be2cd/avatar$224342ca-a8b2-4a9a-8e14-8206253be2cd$female3.fbx";
		var assetRepresentationsAtPath = AssetDatabase.LoadAllAssetRepresentationsAtPath(assetPath);
		foreach (var assetRepresentation in assetRepresentationsAtPath) {
			var animationClip = assetRepresentation as AnimationClip;

			if (animationClip != null) {
				if (animationClip.name.Contains ("RestPose")) { //Found the rest pose created by the blend script, this is great!
					animationClip.SampleAnimation (animator.gameObject, 0); //evaluate the restPose to pose this character before copying it as the restPose restPoseRig
				}
			}
		}

		GameObject restPoseRig = GameObject.Instantiate (baseRig, baseRig.transform);//Make a copy of the armature

		restPoseRig.SetActive (false);

		restPoseRig.name = "RestPoseRig";//rename the copy

		restPoseRig.transform.localScale = Vector3.one;

		baseRig.transform.position = Vector3.zero;
		baseRig.transform.rotation = Quaternion.identity;

		Transform[] allChildren = restPoseRig.GetComponentsInChildren<Transform>();
		foreach (Transform child in allChildren) {

			foreach (var comp in child.GetComponents<ConfigurableJoint>()) { //rigid bodies depens on this, so remove them all first
				GameObject.DestroyImmediate (comp);
			}
			foreach (var comp in child.GetComponents<CharacterJoint>()) { //rigid bodies depens on this, so remove them all first
				GameObject.DestroyImmediate (comp);
			}

			foreach (var comp in child.GetComponents<Component>()) {
				if (!(comp is Transform || comp is SkinnedMeshRenderer )) {
					GameObject.DestroyImmediate (comp);
				}
			}
		}	

		return restPoseRig;
	}


	static void OnPostprocessAllAssets(string[] importedAssets, string[] deletedAssets, string[] movedAssets, string[] movedFromAssetPaths)
	{
		foreach (string importedAssetPath in importedAssets)
		{

            if (Path.GetExtension (importedAssetPath) == ".meta") {
				continue;
			}

            string assetPath = importedAssetPath.Replace ('/', Path.DirectorySeparatorChar); //fix the path so that it uses the correct seperator for this system

            string assetFileName = Path.GetFileName (assetPath);
			string[] split = assetFileName.Split (templateSeperator);

			if (split.Length != 3) {
				continue;
			}

			string uuid = split[1];
			string assetName = split[2];

			string assetFolder = Path.GetDirectoryName (assetPath);


	
			if (assetPath.StartsWith (processingFolder)) {//Looking for the copied .fbx file that resides in the projects processing/prefab folder


				if (!assetPath.EndsWith (".fbx", StringComparison.OrdinalIgnoreCase)) {//only check if .fbx is in the processing folder
					continue;
				}
				GameObject modelAsset = AssetDatabase.LoadAssetAtPath<GameObject> (assetPath); //LOADING AN ASSET


				//ENFORCE REST-POSE SECTION (FIRST IMPORT - CHARACTER TYPE == GENERIC):
				ModelImporter modelImporter = ModelImporter.GetAtPath (assetPath) as ModelImporter;

				if (!modelImporter.userData.Contains (reimportTag)) {//SampleAnimation() is wrong for humanoid rigs??? https://forum.unity.com/threads/sampleanimation-is-wrong.723710/		
					GameObject modelGeneric = (GameObject)PrefabUtility.InstantiatePrefab(modelAsset);
					GameObject realGeneric = GameObject.Instantiate(modelGeneric); //this is a game object that we can re-arange and change parenting or objects, then save as the original prefab later on
					var armatureGeneric = realGeneric.transform.root.GetComponentInChildren<Animator>();
					armatureGeneric.name = modelGeneric.name; //remove "(clone) or any other discrepancies from name"

					GameObject.DestroyImmediate (modelGeneric); //destroy the prefab as it will be overwritten by "real"

					var restPose = CreateRestPoseRig(realGeneric, assetPath); //this is a game object that we can re-arange and change parenting or objects, then save as the original prefab later on;

					foreach (var transform in restPose.GetComponentsInChildren<Transform>()) {
						transform.name = "RestPoseRig_" + transform.name; //must rename each bone so the seriously bugged Unity animator does not try to use them instead of the actual character!! weird 
					}

					string modelFileNameGeneric = Path.GetFileNameWithoutExtension( assetPath );
					string destinationPathGeneric = Path.Combine(prefabsFolder, modelFileNameGeneric + ".prefab");

					PrefabUtility.SaveAsPrefabAsset (restPose, destinationPathGeneric);

					GameObject.DestroyImmediate (realGeneric);

					//modelImporter.animationType = ModelImporterAnimationType.Human;
					modelImporter.userData = modelImporter.userData + " " + reimportTag; //Add reimportTag tag to change the character type to ModelImporterAnimationType.Human
					modelImporter.SaveAndReimport ();
					return;
				} 

				//CONTINUE BUILDING CHARACTER SECTION (SECOND IMPORT - CHARACTER TYPE == HUMANOID):

				string jsonPath = Path.Combine (assetBundlesFolder, uuid+".json");

				if (!File.Exists (jsonPath)) {
					Debug.LogError ("SKIPPING - The JSON file did not exist at path: " + jsonPath);
					continue;
				}

				string jsonTxt = File.ReadAllText(jsonPath);
				AssetBundleUserJson userPrefs = (AssetBundleUserJson) JsonUtility.FromJson (jsonTxt, typeof(AssetBundleUserJson));

				ArmatureLinker.CharacterType characterType;

				switch (userPrefs.variantTag) {
				case ReallusionAssetVariantTag:
					characterType = ArmatureLinker.CharacterType.REALLUSION;
					break;
				case MakehumanAssetVariantTag:
					characterType = ArmatureLinker.CharacterType.MAKEHUMAN;
					break;
				default:
					Debug.LogError ("Non-templateType detected - Filename must begine with a skeleton template type!");
					return;
				}

				if (!modelImporter.userData.Contains (mappedTag)) {
					ApplyTemplateSkeleton (modelImporter, modelAsset, characterType); //Set the humandescription bone overrides (only needed for consistancy) // set "enforce-tpose" and begin the reimport
					try {
						ApplyTemplateSkeleton (modelImporter, modelAsset, characterType); //Set the humandescription bone overrides (only needed for consistancy) // set "enforce-tpose" and begin the reimport
					} finally {
						modelImporter.userData = modelImporter.userData + " " + mappedTag;
						modelImporter.SaveAndReimport ();
					}

					return; //re-import - this will ensure that the human description is updated! Must re-import or else finger bones might be worng (as well as other things)
				}

				//RE-IMPORTED SECTION (SECOND-IMPORT):
				if (!Directory.Exists (prefabsFolder)) {
					Directory.CreateDirectory (prefabsFolder);
				}

				string modelFileName = Path.GetFileNameWithoutExtension( assetPath );
				string destinationPath = Path.Combine(prefabsFolder, modelFileName + ".prefab");

				GameObject model = (GameObject)PrefabUtility.InstantiatePrefab(modelAsset);
				GameObject real = GameObject.Instantiate(model); //this is a game object that we can re-arange and change parenting or objects, then save as the original prefab later on

				real.name = model.name; //remove "(clone) or any other discrepancies from name"

				GameObject.DestroyImmediate (model); //destroy the prefab as it will be overwritten by "real"




				string modelFileNameRestPose = Path.GetFileNameWithoutExtension( assetPath );
				string destinationPathRestPose = Path.Combine(prefabsFolder, modelFileNameRestPose + ".prefab");

				var restPosePrefab = PrefabUtility.LoadPrefabContents (destinationPathRestPose);
				GameObject restPosePrefabReal = GameObject.Instantiate(restPosePrefab); //this is a game object that we can re-arange and change parenting or objects, then save as the original prefab later on
				restPosePrefabReal.name = "RestPoseRig"; //remove "(clone) or any other discrepancies from name"




				//Build the character and set all data arrays
				var buildMakeHuman = real.AddComponent<BuildAvatar> ();

				buildMakeHuman.CreateEmptyContianers (real.name, characterType);

				GameObject.DestroyImmediate (buildMakeHuman); //no long need this component, so destroy it.



				string blenderJsonPath = Path.Combine (assetFolder, "blender.json");

				Dictionary<string, MaterialsJson> materialsJson = null;

				if (File.Exists (blenderJsonPath)) {
					BlenderJsonObject blenderJsonArray = JsonUtility.FromJson<BlenderJsonObject> (
						File.ReadAllText (blenderJsonPath)
					);

					materialsJson = BuildMaterialsDict (blenderJsonArray.materials);
				}	

				var childrenRenderers = real.GetComponentsInChildren<Renderer>();

				//ArmatureLinker linker = animator.transform.GetComponentInChildren<ArmatureLinker> ();

				MakehumanRenderer[] makehumanRenderers = new MakehumanRenderer[childrenRenderers.Length];


				List<string> bonesList = new List<string> ();

				//foreach (Renderer renderer in childrenRenderers) {

				for (int i = 0; i < childrenRenderers.Length; i++) {
					Renderer renderer = childrenRenderers [i];

					makehumanRenderers [i] = new MakehumanRenderer {
						renderer = renderer,
						type = MakehumanMeshBoneType.none
					};

					var skinnedRenderer = renderer.GetComponent<SkinnedMeshRenderer> ();
					if (skinnedRenderer == null) {
						continue;
					}
					skinnedRenderer.updateWhenOffscreen = true; //always do this for all characters so they will be visible to camcorders
					
					var weights = skinnedRenderer.sharedMesh.boneWeights;
					//var allBones = skinnedRenderer.bones;

					bonesList.Clear ();

					foreach (var weight in weights) {
						var bIdx = weight.boneIndex0;
						var bTran = skinnedRenderer.bones [bIdx];

						if (!bonesList.Contains (bTran.name)) {
							bonesList.Add (bTran.name);
							//Debug.Log ("bTran " + bTran.name);
						}
					}

					switch (userPrefs.variantTag) {
					case ReallusionAssetVariantTag:

						if (bonesList.Count == 2 &&
						    new string[] {
								"CC_Base_R_Eye",
								"CC_Base_L_Eye"
						}.All (n => bonesList.Contains (n))) {
							//Debug.Log ("I THINK THIS IS AN EYE");
							makehumanRenderers [i].type = MakehumanMeshBoneType.eyeballs;
							continue;
						}

						if (bonesList.Count == 2 &&
						    new string[] {
								"CC_Base_Teeth01",
								"CC_Base_Teeth02"
						}.All (n => bonesList.Contains (n))) {
							//Debug.Log ("I THINK THIS IS TEETH");
							makehumanRenderers [i].type = MakehumanMeshBoneType.teeth;
							continue;
						}

						if (bonesList.Count == 3 &&
						    new string[] {
								"CC_Base_Tongue01",
								"CC_Base_Tongue02",
								"CC_Base_Tongue03"
						}.All (n => bonesList.Contains (n))) {
							//Debug.Log ("I THINK THIS IS A TONGUE");
							makehumanRenderers [i].type = MakehumanMeshBoneType.tongue;
							continue;
						}
						break;
					case MakehumanAssetVariantTag:
						
						if (bonesList.Count == 2 &&
						    new string[] {
								"eye.R",
								"eye.L"
						}.All (n => bonesList.Contains (n))) {
							//Debug.Log ("I THINK THIS IS AN EYE");
							makehumanRenderers [i].type = MakehumanMeshBoneType.eyeballs;
							continue;
						}

						if (bonesList.Count == 5 &&
						    new string[] {
								"head",
								"orbicularis03.R",
								"orbicularis03.L",
								"orbicularis04.R",
								"orbicularis04.L"
						}.All (n => bonesList.Contains (n))) {
							//Debug.Log ("I THINK THIS IS AN EYELASH");
							makehumanRenderers [i].type = MakehumanMeshBoneType.eyelashes;
							continue;
						}

						if (bonesList.Count == 3 &&
						    new string[] {
								"head",
								"oculi01.R",
								"oculi01.L"
						}.All (n => bonesList.Contains (n))) {
							//Debug.Log ("I THINK THIS IS AN EYEBROW");
							makehumanRenderers [i].type = MakehumanMeshBoneType.eyebrows;
							continue;
						}

						if (bonesList.Count == 2 &&
						    new string[] {
								"jaw",
								"head"
						}.All (n => bonesList.Contains (n))) {
							//Debug.Log ("I THINK THIS IS TEETH");
							makehumanRenderers [i].type = MakehumanMeshBoneType.teeth;
							continue;
						}

						if (bonesList.Count == 10 &&
						    new string[] {
								"tongue07.R",
								"tongue04",
								"tongue07.L",
								"tongue03",
								"tongue06.L",
								"tongue05.L",
								"tongue02",
								"tongue01",
								"tongue06.R",
								"tongue05.R"
						}.All (n => bonesList.Contains (n))) {
							//Debug.Log ("I THINK THIS IS A TONGUE");
							makehumanRenderers [i].type = MakehumanMeshBoneType.tongue;
							continue;
						}
						break;
					}
				}


				//foreach (Renderer renderer in childrenRenderers) {
				foreach (MakehumanRenderer makehumanRenderer in makehumanRenderers) {
					var renderer = makehumanRenderer.renderer;
					if (renderer == null) {
						continue;
					}

					renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
					renderer.receiveShadows = true;

					foreach (var material in renderer.sharedMaterials) {

						//var material = renderer.sharedMaterial;

						var mainColor = material.GetColor ("_Color");
						mainColor.a = 1.0f; //always do this, just because unity is weird and seemingly random alpha values always appear
						material.SetColor ("_Color", mainColor);


						if (materialsJson != null) {
							//THE NEW WAY (USING BLENDER MATERIALS JSON)
							//var textureFileName = Path.GetFileName (AssetDatabase.GetAssetPath (material.mainTexture)); //takes a full path to an texture asset, and returs the filename with extension (which is used as key for materials json)
							var was = Path.GetFileName (AssetDatabase.GetAssetPath (material.mainTexture));
							var materialName = material.name;// Path.GetFileName (AssetDatabase.GetAssetPath (material.mainTexture)); //takes a full path to an texture asset, and returs the filename with extension (which is used as key for materials json)
							if (material.mainTexture != null) {
								materialName = Path.GetFileName (AssetDatabase.GetAssetPath (material.mainTexture)); //takes a full path to an texture asset, and returs the filename with extension (which is used as key for materials json)
							}
							materialName = Path.GetFileNameWithoutExtension (materialName);

							if (materialsJson.ContainsKey (materialName)) {		

								//if (materialsJson.ContainsKey (textureFileName)) {

								//var blenderMaterial = materialsJson [textureFileName];
								var blenderMaterial = materialsJson [materialName];


								Texture2D diffTex = null;
								Texture2D bumpTex = null;
								Texture2D specularTex = null;
								Texture2D emissionTex = null;

								bool enableAlpha = false;
								float emit_factor = 0;

								var use_map_color_diffuse = false;
								var use_map_bump = false;
								var use_map_specular = false;
								var use_map_emit = false;

								foreach (var slot in blenderMaterial.texture_slots) { //check all slots to see if there are any spec or emmit textures
									if (slot.use_map_color_diffuse) {										
										//Debug.Log ("use_map_color_diffuse " + slot.filename);
										//var texPath = AssetDatabase.GetAssetPath (material.mainTexture);
										var texPath = Path.Combine (Path.GetDirectoryName (assetPath), slot.filename);
										if (File.Exists (texPath)) {
											var folder = Path.GetDirectoryName (texPath);
											diffTex = AssetDatabase.LoadAssetAtPath (Path.Combine (folder, slot.filename), typeof(Texture2D)) as Texture2D;

											TextureImporter A = (TextureImporter)AssetImporter.GetAtPath (Path.Combine (folder, slot.filename));
											enableAlpha = blenderMaterial.use_transparency && A.DoesSourceTextureHaveAlpha ();
										}
									}
									if (slot.use_map_normal) {		
										//Debug.Log("use_map_normal " + slot.filename);
										//var texPath = AssetDatabase.GetAssetPath (material.mainTexture);
										var texPath = Path.Combine (Path.GetDirectoryName (assetPath), slot.filename);
										if (File.Exists (texPath)) {
											var folder = Path.GetDirectoryName (texPath);
											bumpTex = AssetDatabase.LoadAssetAtPath (Path.Combine (folder, slot.filename), typeof(Texture2D)) as Texture2D;
										}			
									}
									if (slot.use_map_specular) {
										//Debug.Log("use_map_specular " + slot.filename);
										//var texPath = AssetDatabase.GetAssetPath (material.mainTexture);
										var texPath = Path.Combine (Path.GetDirectoryName (assetPath), slot.filename);
										if (File.Exists (texPath)) {
											var folder = Path.GetDirectoryName (texPath);
											specularTex = AssetDatabase.LoadAssetAtPath (Path.Combine (folder, slot.filename), typeof(Texture2D)) as Texture2D;
										}
									}
									if (slot.use_map_emit) {
										//Debug.Log("use_map_emit " + slot.filename);
										//var texPath = AssetDatabase.GetAssetPath (material.mainTexture);
										var texPath = Path.Combine (Path.GetDirectoryName (assetPath), slot.filename);
										if (File.Exists (texPath)) {
											var folder = Path.GetDirectoryName (texPath);							
											emissionTex = AssetDatabase.LoadAssetAtPath (Path.Combine (folder, slot.filename), typeof(Texture2D)) as Texture2D;
										}
										emit_factor = slot.emit_factor;
									}

									use_map_color_diffuse |= slot.use_map_color_diffuse;
									use_map_bump |= slot.use_map_normal;
									use_map_specular |= slot.use_map_specular;
									use_map_emit |= slot.use_map_emit;
								}

								var specIsBlack = 
									(blenderMaterial.specular_color.r * blenderMaterial.specular_intensity) == 0
									&&
									(blenderMaterial.specular_color.g * blenderMaterial.specular_intensity) == 0
									&&
									(blenderMaterial.specular_color.b * blenderMaterial.specular_intensity) == 0;

								if (!specIsBlack || use_map_specular) {
									material.shader = Shader.Find ("Standard (Specular setup)"); //the default fallback shader
									material.SetColor ("_SpecColor", new Color (
										blenderMaterial.specular_color.r * blenderMaterial.specular_intensity * 0.25f,//default values are way too high for Standard shader so multiply by 0.25
										blenderMaterial.specular_color.g * blenderMaterial.specular_intensity * 0.25f,
										blenderMaterial.specular_color.b * blenderMaterial.specular_intensity * 0.25f
									));


								}

								if (use_map_color_diffuse) { //set all white and adjust brightness based on diffuse intensity set from blender
									material.SetColor ("_Color", new Color (
										blenderMaterial.diffuse_intensity,
										blenderMaterial.diffuse_intensity,
										blenderMaterial.diffuse_intensity,
										blenderMaterial.alpha
									));
								} else { 
									material.SetColor ("_Color", new Color (// has no texture, thus pass through the color and adjust on diffuse intensity set from blender
										mainColor.r * blenderMaterial.diffuse_intensity,
										mainColor.g * blenderMaterial.diffuse_intensity,
										mainColor.b * blenderMaterial.diffuse_intensity,
										blenderMaterial.alpha
									));

									if (blenderMaterial.use_transparency) { //has no texture but alpha was set, so ensure to honor that
										enableAlpha = true;
									}
								}

								if (enableAlpha) {//change to opaque https://sassybot.com/blog/swapping-rendering-mode-in-unity-5-0/

									material.SetInt ("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One);
									material.SetInt ("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
									material.SetInt ("_ZWrite", 0);
									material.DisableKeyword ("_ALPHATEST_ON");
									material.DisableKeyword ("_ALPHABLEND_ON");
									material.EnableKeyword ("_ALPHAPREMULTIPLY_ON");
									material.renderQueue = 3000;

								} else { //OPAQUE

									material.SetInt ("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One);
									material.SetInt ("_DstBlend", (int)UnityEngine.Rendering.BlendMode.Zero);
									material.SetInt ("_ZWrite", 1);
									material.DisableKeyword ("_ALPHATEST_ON");
									material.DisableKeyword ("_ALPHABLEND_ON");
									material.DisableKeyword ("_ALPHAPREMULTIPLY_ON");
									material.renderQueue = -1;

								}
									
								if (use_map_color_diffuse) {
									material.SetTexture ("_MainTex", diffTex);
								}
								if (use_map_bump) {
									material.SetTexture ("_BumpMap", bumpTex);
								}
								if (use_map_emit) {
									material.EnableKeyword ("_EMISSION"); //You must enable the correct Keywords for your required Standard Shader variant
									material.SetTexture ("_EmissionMap", emissionTex);
									material.SetColor ("_EmissionColor", new Color (
										emit_factor,
										emit_factor,
										emit_factor
									));
								}

								if (use_map_specular) {
									material.EnableKeyword ("_SPECGLOSSMAP"); //You must enable the correct Keywords for your required Standard Shader variant
									material.SetTexture ("_SpecGlossMap", specularTex);
								}

								material.SetFloat ("_GlossMapScale", blenderMaterial.specular_hardness / 511f);
								material.SetFloat ("_Glossiness", blenderMaterial.specular_hardness / 511f);
								material.SetFloat ("_Shininess", blenderMaterial.specular_hardness / 511f); //synonmus with _Glossiness if using legacy shaders

								if (!use_map_specular && !use_map_emit) {

									/*if (blenderMaterial.key.ToLower ().Contains ("hair")) {
										material.shader = Shader.Find ("Hair/Standard Two Sided Soft Blend");
										material.SetFloat ("_Cutoff", 0.05f);
									} else if (
										blenderMaterial.key.ToLower ().Contains ("eye") && (
											blenderMaterial.key.ToLower ().Contains ("lash")
											||
											blenderMaterial.key.ToLower ().Contains ("brow")
										)) { //if its hair sprites
										material.shader = Shader.Find ("Sprites/Default");
										continue; //it's no longer a stander shader, nothing more to be done
									}*/

									if (blenderMaterial.key.ToLower ().Contains ("hair")) {
										material.shader = Shader.Find ("Hair/Standard Two Sided Soft Blend");
										material.SetFloat ("_Cutoff", 0.05f);
									}

									switch (userPrefs.variantTag) {
									case ReallusionAssetVariantTag:
										if (	blenderMaterial.key.ToLower ().Contains ("eye") && (
												blenderMaterial.key.ToLower ().Contains ("lash")
												||
												blenderMaterial.key.ToLower ().Contains ("brow")
											)) { //if its hair sprites
											material.shader = Shader.Find ("Sprites/Default");
											continue; //it's no longer a stander shader, nothing more to be done
										}
									break;
									}

									if (makehumanRenderer.type != MakehumanMeshBoneType.none) {
										renderer.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
										renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;


										switch (makehumanRenderer.type) {
										case MakehumanMeshBoneType.eyeballs:	
											foreach (var mat in makehumanRenderer.renderer.sharedMaterials) {
												mat.renderQueue = 2450; //this prevents the eyes from "glowing" in some scenes..
											}
											break;
										case MakehumanMeshBoneType.eyebrows:
										case MakehumanMeshBoneType.eyelashes:
											material.shader = Shader.Find ("Sprites/Default");				
											break;
										case MakehumanMeshBoneType.teeth:
										case MakehumanMeshBoneType.tongue:
											if (renderer.GetComponent<SkinnedMeshRenderer> ()) {
												renderer.GetComponent<SkinnedMeshRenderer> ().updateWhenOffscreen = false;
											}
											break;
										}


									} 
								}



							}

						} else {
							/*
							material.shader = Shader.Find ("Standard (Specular setup)"); //the default fallback shader
							//THE OLD WAY - USE KEYWORDS IN MATERIAL NAME TO CONTROL SHADER KEYWORDS

							var color222 = material.GetColor ("_Color");

							color222.a = 1.0f; //always do this, just because unity is weird and seemingly random alpha values always appear
							material.SetColor ("_Color", color222);

							if (material.mainTexture != null) {

								string path = AssetDatabase.GetAssetPath (material.mainTexture);
								TextureImporter A = (TextureImporter)AssetImporter.GetAtPath (path);

								if (!A.DoesSourceTextureHaveAlpha ()) {//change to opaque https://sassybot.com/blog/swapping-rendering-mode-in-unity-5-0/
									material.SetInt ("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One);
									material.SetInt ("_DstBlend", (int)UnityEngine.Rendering.BlendMode.Zero);
									material.SetInt ("_ZWrite", 1);
									material.DisableKeyword ("_ALPHATEST_ON");
									material.DisableKeyword ("_ALPHABLEND_ON");
									material.DisableKeyword ("_ALPHAPREMULTIPLY_ON");
									material.renderQueue = -1;
								}

								var matTextureName = material.mainTexture.name.ToLower ();
								//Debug.Log ("MAT NAME " + matTextureName);
								var texPath = AssetDatabase.GetAssetPath (material.mainTexture);
								var texName = Path.GetFileNameWithoutExtension (texPath);

								//Debug.Log ("matTextureName" + matTextureName);
								//Debug.Log ("Texture Path" + texPath);

								Texture specularTex = GetFileByKeywords (texPath, new[] {
									"_Spec",
									"_spec",
									"_Specularity",
									"_specularity",
									"_Specular",
									"_specular"
								});
								Texture metallicTex = GetFileByKeywords (texPath, new[] { "_Metallic", "_metallic" });

								if (specularTex != null) {
									//Debug.Log ("JUST SET SPECULAR SETUP!! " + specularTex);
									material.shader = Shader.Find ("Standard (Specular setup)");
									material.EnableKeyword ("_SPECGLOSSMAP"); //You must enable the correct Keywords for your required Standard Shader variant
									material.SetTexture ("_SpecGlossMap", specularTex);
									material.SetColor ("_SpecColor", Color.white);
								} else {
									if (metallicTex != null) {
										material.EnableKeyword ("_METALLICGLOSSMAP"); //You must enable the correct Keywords for your required Standard Shader variant
										material.SetTexture ("_MetallicGlossMap", metallicTex);
									}
								}

								Texture emissionTex = GetFileByKeywords (texPath, new[] { "_Emission", "_emission" });
								if (emissionTex != null) {
									material.EnableKeyword ("_EMISSION"); //You must enable the correct Keywords for your required Standard Shader variant
									material.SetTexture ("_EmissionMap", emissionTex);
									material.SetColor ("_EmissionColor", Color.white);
								}

								if (specularTex == null && emissionTex == null) {
									if (matTextureName.Contains ("_hair")) {
										material.shader = Shader.Find ("Custom/Standard Two Sided Soft Blend");
										material.SetFloat ("_Cutoff", 0.05f);
									} else if (
										matTextureName.Contains ("eyelash") ||
										matTextureName.Contains ("eyebrow")) { //if its hair sprites
										material.shader = Shader.Find ("Sprites/Default");
										continue; //it's no longer a stander shader, nothing more to be done
									}
								}
							}


							if (material.HasProperty ("_Mode") && material.GetFloat ("_Mode").Equals (3)) { //if the exported material has transparency
								//Debug.Log ("MODE 3 " + material);
								if (color222.a >= 0.9f) { //because blender/unity are weird, and setting blender to 1 results in unity using opaque mode
									color222.a = 1.0f;
									material.SetColor ("_Color", color222);
								}
								//material.SetFloat("_Mode", 3);
								//material.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
								//material.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
								//material.SetInt("_ZWrite", 0);
								//material.DisableKeyword("_ALPHATEST_ON");
								//material.EnableKeyword("_ALPHABLEND_ON");
								//material.DisableKeyword("_ALPHAPREMULTIPLY_ON");
								//material.renderQueue = 3000;
							}
							*/
						}

					}

					//var shaderParams = renderer.gameObject.AddComponent<RendererShaderParams> ();
					//shaderParams.StoreParams (); //NOW USING RendererShaderParams.StoreAllRenderers (real);
				
				}


				RendererShaderParams.StoreAllRenderers (real);

				
				var defaultController = Resources.Load<RuntimeAnimatorController>("DefaultAnimationController");
				if (defaultController != null) {
					var animator = real.transform.root.GetComponentInChildren<Animator> ();
					animator.runtimeAnimatorController = defaultController;
				}

				var armature = real.transform.root.GetComponentInChildren<ArmatureLinker>();
				armature.restPose = restPosePrefabReal;// CreateRestPoseRig(real, assetPath); //this is a game object that we can re-arange and change parenting or objects, then save as the original prefab later on;
				restPosePrefabReal.transform.parent = real.transform;


				//parse and store mhx facial rig drivers and scripted expressions
				Dictionary<string, ArmatureLinker.ExpessionsJson> expressionsJson = null;
				if (File.Exists (blenderJsonPath)) {
					BlenderJsonObject blenderJsonArray = JsonUtility.FromJson<BlenderJsonObject> (
						File.ReadAllText (blenderJsonPath)
					);

					expressionsJson = blenderJsonArray.expressions.ToDictionary (x => x.bone_name, x => x);//convert KeyValuePair to Dictionary - https://stackoverflow.com/a/18955562/3961748

					List<ArmatureLinker.ExpessionsJson> expressionsData = new List<ArmatureLinker.ExpessionsJson>();
					foreach (var expression in blenderJsonArray.expressions) {//   expressionsJson.Keys) {
						var bone_name = expression.bone_name;

						var driversX = new ArmatureLinker.Driver[expressionsJson [bone_name].drivers.x.Count ()]; //a temp array to store the drivers as interated from the json file
						for (int i = 0; i < expressionsJson[bone_name].drivers.x.Count(); i++) {//build a temp formatted array for extracting the list of drivers and their polynomial components
							driversX[i] = new ArmatureLinker.Driver() {
								c = expressionsJson[bone_name].drivers.x[i].c,
								v = expressionsJson[bone_name].drivers.x[i].v
							};
						}

						var driversY = new ArmatureLinker.Driver[expressionsJson [bone_name].drivers.y.Count ()]; //a temp array to store the drivers as interated from the json file
						for (int i = 0; i < expressionsJson[bone_name].drivers.y.Count(); i++) {//build a temp formatted array for extracting the list of drivers and their polynomial components
							driversY[i] = new ArmatureLinker.Driver() {
								c = expressionsJson[bone_name].drivers.y[i].c,
								v = expressionsJson[bone_name].drivers.y[i].v
							};
						}

						var driversZ = new ArmatureLinker.Driver[expressionsJson [bone_name].drivers.z.Count ()]; //a temp array to store the drivers as interated from the json file
						for (int i = 0; i < expressionsJson[bone_name].drivers.z.Count(); i++) {//build a temp formatted array for extracting the list of drivers and their polynomial components
							driversZ[i] = new ArmatureLinker.Driver() {
								c = expressionsJson[bone_name].drivers.z[i].c,
								v = expressionsJson[bone_name].drivers.z[i].v
							};
						}


						ArmatureLinker.DriverAxis driversAll = new ArmatureLinker.DriverAxis() {
							x = driversX,
							y = driversY,
							z = driversZ
						}; 

						expressionsData.Add (new ArmatureLinker.ExpessionsJson () {
							bone = armature.head.FindDeepChild(bone_name),
							bone_name = bone_name,
							drivers = driversAll			
						});
					}
					armature.expressionsData = expressionsData.ToArray();//store the facial expressions data to the armature for loading during runtime

				}
			
				if (modelImporter.userData.Contains (processedTag)) {
					string json = JsonUtility.ToJson(userPrefs);	
					using (StreamWriter sr = new StreamWriter(jsonPath)) // Create the file.
					{	
						sr.WriteLine (json);
					}
				}

				PrefabUtility.SaveAsPrefabAsset (real, destinationPath);

				GameObject.DestroyImmediate (real);

			} else if (assetPath.StartsWith (prefabsFolder)) { //ASSET BUNDLE FINAL PROCESSING 
				
				var assetImport = AssetImporter.GetAtPath (assetPath);
				assetImport.SetAssetBundleNameAndVariant(Path.GetFileNameWithoutExtension(assetPath), AssetBundleVariant);

			} else if (assetPath.StartsWith (assetBundlesFolder)) { //ASSET BUNDLE FINAL PROCESSING 

                Debug.Log("assetPath.StartsWith (assetBundlesFolder)");
				if (!Path.GetExtension (assetPath).Contains (AssetBundleVariant)) {
					continue; //might be a .meta file, just ignore it
				}

				var rootObjs = new List<GameObject>();
				foreach (var item in UnityEngine.SceneManagement.SceneManager.GetActiveScene ().GetRootGameObjects ()) {
					if (item.activeSelf) { //only store active go's, so that we may disable them during portrait pictures, them re-enable them
						rootObjs.Add(item);
					}
				}
					
				string assetDestFolder = Path.Combine (assetBundlesFolder, Path.GetFileNameWithoutExtension(assetPath).ToLower() );
                Debug.Log("assetDestFolder " + assetDestFolder);
                string jsonPath = Path.Combine (assetFolder, uuid+".json");
				if (!File.Exists (jsonPath)) {
                    Debug.Log("Path.GetDirectoryName (assetPath)" + Path.GetDirectoryName(assetPath));
                    Debug.Log("assetBundlesFolder " + assetBundlesFolder);
 
                    if (Path.GetDirectoryName (assetPath).Equals(assetBundlesFolder)) {
					
                    //if (Path.GetFullPath(Path.GetDirectoryName (assetPath)).Equals(Path.GetFullPath(assetBundlesFolder))) {
						if (Directory.Exists (assetDestFolder)) {
                            FileUtil.DeleteFileOrDirectory( Path.Combine (assetDestFolder, assetFileName));
							File.Move(assetPath, Path.Combine (assetDestFolder, assetFileName));

							var thumbnailFolderAbs = Path.Combine (assetDestFolder, "thumbnails");
                            TakePortraitPictures (assetFileName, rootObjs, thumbnailFolderAbs); //update the portrait pictures

							AssetDatabase.Refresh ();
							continue;
						}

					} else {
						continue;
					}

					Debug.LogWarning ("SKIPPING - The JSON file did not exist at path: " + jsonPath);
					continue;
				}
				string jsonTxt = File.ReadAllText(jsonPath);
				AssetBundleUserJson userPrefs = (AssetBundleUserJson) JsonUtility.FromJson (jsonTxt, typeof(AssetBundleUserJson));
				File.Delete (jsonPath);//no longer needed

                var to = Path.Combine(assetDestFolder, assetFileName);
                Debug.Log("CreateDirectory " + Path.GetDirectoryName(to));
				if (!Directory.Exists(Path.GetDirectoryName(to))) {
					Directory.CreateDirectory (Path.GetDirectoryName(to));
				}

				if (File.Exists (to)) {
					File.Delete (to);
				}

				FileUtil.MoveFileOrDirectory(assetPath,	to);	

				DirectoryInfo dir = new DirectoryInfo(Path.GetDirectoryName(assetPath));
				FileInfo[] info = dir.GetFiles( Path.GetFileNameWithoutExtension(assetFileName) + ".*");
				foreach (FileInfo f in info) {
					File.Delete (f.FullName);
				}
					
				var thumbnailFolder = Path.Combine (assetDestFolder, "thumbnails");
				TakePortraitPictures (assetFileName, rootObjs, thumbnailFolder); //take the initial portrait pictures

				//copy the .blend character file to the final assetbundle directory if it exists
				DirectoryInfo dir_blend = new DirectoryInfo (userPrefs.characterFolder);
				FileInfo blendInfo = dir_blend.GetFiles (Path.GetFileNameWithoutExtension(assetName) + ".blend").FirstOrDefault();

				if (blendInfo == null) {
					Debug.LogWarning (String.Format("{0}.blend file could be copied.", Path.GetFileNameWithoutExtension(assetName)));
				} else {
					ZipFile.Compress (new FileInfo(blendInfo.FullName));

					if (File.Exists(blendInfo.FullName+".gz")) {
						var path_blend_gz = Path.Combine (assetDestFolder, Path.GetFileNameWithoutExtension(assetFileName) + ".blend.gz");

						FileUtil.MoveFileOrDirectory (blendInfo.FullName+".gz", path_blend_gz);
					}

				}

				AssetDatabase.Refresh ();

				AnimPrepAssetBuilder.ShowExplorer (assetDestFolder);

			} else {
				Debug.LogWarning (assetPath + " - WAS NOT A MEMBER OF FOLDERS: " + assetBundlesFolder + " - OR - " + processingFolder);
			} 

			EditorUtility.UnloadUnusedAssetsImmediate ();
			System.GC.Collect ();

		}


	}

	static void TakePortraitPictures(string assetFileName, List<GameObject> rootObjs, string destFolder) {

		string prefabPath = Path.Combine(prefabsFolder, Path.GetFileNameWithoutExtension(assetFileName) + ".prefab");

		UnityEngine.Object prefab = AssetDatabase.LoadAssetAtPath(prefabPath, typeof(GameObject));

		GameObject clone = GameObject.Instantiate(prefab, Vector3.zero, Quaternion.identity) as GameObject;
		clone.name += "_PHOTO_RIG";

		var armature = clone.GetComponentInChildren<ArmatureLinker> (); //test to ensure the user properly applied scale
		if (armature == null) {
			Debug.LogError (string.Format ("Armature Null Error"));
		} else {

			if (Vector3.Distance(clone.transform.localScale, Vector3.one) > 0.01 //if the obj scale is not roughly 1,1,1 
				||
				Vector3.Distance(armature.transform.localScale, Vector3.one) > 0.01	//if the armature scale is not roughly 1,1,1 				
			) {
				Debug.LogError (string.Format ("The armature's scale was not normalized (This is critical!!), ensure to export from Blender with: \"Apply Scale\" == FBX All"));
			}

		}

		var portraitCameraPrefabPath = "Assets/AnimPrep/Prefabs/PortraitCameraPrefab.prefab";

		UnityEngine.Object portraitCameraPrefab = AssetDatabase.LoadAssetAtPath(portraitCameraPrefabPath, typeof(GameObject));
		GameObject portraitCameraObject = GameObject.Instantiate(portraitCameraPrefab, Vector3.zero, Quaternion.identity) as GameObject;


		//var portraitFileName = "portrait_";// Path.GetFileNameWithoutExtension (assetFileName);

		if (portraitCameraObject != null) { //if for some reason the proper scene is not loaded and the protrait camera is missing...

			clone.transform.localPosition = Vector3.zero;

			var portraitCamera = portraitCameraObject.GetComponentInChildren<TakeScreenshot>();

			portraitCamera.m_camera.clearFlags = CameraClearFlags.Skybox;

			//Take some thumbnail pictures of the prefab before destroying it.
			foreach (GameObject go in rootObjs) {//ensure there are no other objects in the scene prior to taking portraits
				go.SetActive(false);
			}

			try {
				int frames = 25;
				frames += 1; //add one because the for loop uses a < instead of a <= so as to skip the last frame

				portraitCamera.m_camera.clearFlags = CameraClearFlags.SolidColor;
				portraitCamera.m_sceneObject = clone.transform;
				clone.transform.position = Vector3.zero;
				clone.transform.rotation = Quaternion.identity;

				for (int i = 0; i < frames; i++ ) {
					var t = i / (float)frames;
					portraitCamera.EvaluateCurve(clone.transform, t);
					portraitCamera.CamCapture (Path.Combine (destFolder, string.Format("thumbnail_{0}.png", i)));
				}

				GameObject.DestroyImmediate (portraitCameraObject);

			} finally {
				foreach (GameObject go in rootObjs) {
					go.SetActive (true);
				}
			}

			GameObject.DestroyImmediate(clone);
				
		}
	}

}

#endif