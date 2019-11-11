using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

#if UNITY_EDITOR
using UnityEditor;
[CustomEditor(typeof(ArmatureLinker))]
[CanEditMultipleObjects]
public class ArmatureLinkerEditor : Editor 
{


	public override void OnInspectorGUI()
	{

		DrawDefaultInspector();
		
		ArmatureLinker builder = (ArmatureLinker)FindObjectOfType(typeof(ArmatureLinker));
		GUILayout.Space(100);
		if (GUILayout.Button("Delete This Character"))
		{

			var prefab = PrefabUtility.FindPrefabRoot(builder.gameObject);
			string myPath = AssetDatabase.GetAssetPath( builder.gameObject );
			Debug.Log(myPath);
			AssetDatabase.DeleteAsset(myPath);
			Debug.Log(prefab);
		}
		GUILayout.Space(100);
		

	}
}
#endif

public static class TransformDeepChildExtension
{
	//Breadth-first search
	public static Transform FindDeepChild(this Transform aParent, string aName)	{
		var result = aParent.Find(aName);
		if (result != null) {
			return result;
		}
		foreach(Transform child in aParent)	{
			result = child.FindDeepChild(aName);
			if (result != null) {
				return result;
			}
		}
		return null;
	}
}


public class ArmatureLinker : MonoBehaviour
{
	
	public enum CharacterType {
		DEFAULT,
		CC3,
		MAKEHUMAN,
		MIXAMO,
		DAZ3D_G2,
		DAZ3D_G3,
	};
	public CharacterType characterType = CharacterType.DEFAULT;

	[Header("_Armature_")]
	public string defaultModel = "Not_Yet_Set"; //a reference to an actual assetBundle so it's animations can be saved and loaded (Note if the default (non-assetbundle) model is used THIS WILL HAVE TO BE SET in the inspector field manually).

	[Header("Face Blendshapes")]
	public SkinnedMeshRenderer faceRenderer; //the renderer that has the eyelid blend shapes

	//public Transform root;
	[Header("_Torso_")]
	public Transform hip;
	public Transform spine;
	public Transform chest;

	[Header("_Upper_")]
	public Transform neck;
	public Transform head;

	[Header("_Breasts_")]
	public Transform breastL;
	public Transform breastR;
	//public Rigidbody chestRb;

	[Header("_Face Rig (Optional)_")]
	public Transform eyeL;
	public Transform eyelidL;
	public Transform eyeR;
	public Transform eyelidR;
	public Transform jaw;

	[Header("_Right Arm_")]
	public Transform shoulderR;
	public Transform upper_armR;
	public Transform forearmR;


	[Header("_Left Arm_")]
	public Transform shoulderL;
	public Transform upper_armL;
	public Transform forearmL;


	[Header("_Right Leg_")]
	public Transform thighR;
	public Transform shinR;
	public Transform footR;
	public Transform toeR;

	[Header("_Left Leg_")]
	public Transform thighL;
	public Transform shinL;
	public Transform footL;
	public Transform toeL;




	[Header("_Right Hand_")]
	public Transform handR;
	[Header("_Right Fingers_")]
	public Transform indexR;
	public Transform middleR;
	public Transform ringR;
	public Transform pinkyR;
	public Transform thumbR;

	[Header("_Left Hand_")]
	public Transform handL;
	[Header("_Left Fingers_")]
	public Transform indexL;
	public Transform middleL;
	public Transform ringL;
	public Transform pinkyL;
	public Transform thumbL;

	[HideInInspector]
	public GameObject restPose;

	//Makehuman Facial Expressions
	[System.Serializable]
	public struct Driver
	{	
		public float c; //constant
		public string v; //variable
	}

	[System.Serializable]
	public struct DriverAxis //scripted expressions from mhx blender driver
	{
		public Driver[] x;
		public Driver[] y;
		public Driver[] z;
	}

	[System.Serializable]
	public struct ExpessionsJson
	{
		public Transform bone;
		public string bone_name; //facial rig bone
		public DriverAxis drivers; 
	}
	public ExpessionsJson[] expressionsData;


	Transform GetBoneTransform (HumanBodyBones humanBone) {
		return GetComponentInParent<Animator> ().GetBoneTransform (humanBone);
		//return transform.FindDeepChild(MakehumanMappings.mappings.human [System.Array.IndexOf (MakehumanMappings.mappings.boneType, humanBone)].boneName);
	}

	[Serializable]
	public struct BlendShapeParams {
		public string shapeName; //only here (and public) so as to expose this field to the inspector when creating a list of template objects.
		public float shapeWeight;
	}
	public BlendShapeParams[] faceRenderersParams;

	public void PopulateFields (GameObject avatarMesh, CharacterType _characterType) {

		characterType = _characterType;

		hip = GetBoneTransform        (HumanBodyBones.Hips);// this.transform;//
		chest = GetBoneTransform      (HumanBodyBones.Chest);
		spine = GetBoneTransform      (HumanBodyBones.Spine);

		neck = GetBoneTransform       (HumanBodyBones.Neck);
		head = GetBoneTransform       (HumanBodyBones.Head);

		jaw = GetBoneTransform        (HumanBodyBones.Jaw);
		eyeL = GetBoneTransform       (HumanBodyBones.LeftEye);
		eyeR = GetBoneTransform       (HumanBodyBones.RightEye);

		shoulderL = GetBoneTransform  (HumanBodyBones.LeftShoulder);
		upper_armL = GetBoneTransform (HumanBodyBones.LeftUpperArm);
		forearmL = GetBoneTransform   (HumanBodyBones.LeftLowerArm);
		handL = GetBoneTransform      (HumanBodyBones.LeftHand);

		shoulderR = GetBoneTransform  (HumanBodyBones.RightShoulder);
		upper_armR = GetBoneTransform (HumanBodyBones.RightUpperArm);
		forearmR = GetBoneTransform   (HumanBodyBones.RightLowerArm);
		handR = GetBoneTransform      (HumanBodyBones.RightHand);

		thighL = GetBoneTransform     (HumanBodyBones.LeftUpperLeg);
		shinL = GetBoneTransform      (HumanBodyBones.LeftLowerLeg);
		footL = GetBoneTransform      (HumanBodyBones.LeftFoot);
		toeL = GetBoneTransform       (HumanBodyBones.LeftToes);

		thighR = GetBoneTransform     (HumanBodyBones.RightUpperLeg);
		shinR = GetBoneTransform      (HumanBodyBones.RightLowerLeg);
		footR = GetBoneTransform      (HumanBodyBones.RightFoot);
		toeR = GetBoneTransform       (HumanBodyBones.RightToes);

		indexL = GetBoneTransform     (HumanBodyBones.LeftIndexProximal);
		middleL = GetBoneTransform    (HumanBodyBones.LeftMiddleProximal);
		ringL = GetBoneTransform      (HumanBodyBones.LeftRingProximal);
		pinkyL = GetBoneTransform     (HumanBodyBones.LeftLittleProximal);
		thumbL = GetBoneTransform     (HumanBodyBones.LeftThumbProximal);

		indexR = GetBoneTransform     (HumanBodyBones.RightIndexProximal);
		middleR = GetBoneTransform    (HumanBodyBones.RightMiddleProximal);
		ringR = GetBoneTransform      (HumanBodyBones.RightRingProximal);
		pinkyR = GetBoneTransform     (HumanBodyBones.RightLittleProximal);
		thumbR = GetBoneTransform     (HumanBodyBones.RightThumbProximal);

		Transform _breastL;
		Transform _breastR;

		switch (characterType) { 
		case ArmatureLinker.CharacterType.DAZ3D_G2:
		case ArmatureLinker.CharacterType.DAZ3D_G3:
			_breastL = chest.FindDeepChild ("lPectoral"); //From DAZ default skeleton
			if (_breastL != null) {
				breastL = _breastL;
			}

			_breastR = chest.FindDeepChild ("rPectoral"); //From DAZ default skeleton
			if (_breastR != null) {
				breastR = _breastR;
			}

			faceRenderersParams = faceRenderersParams_Daz3D;
			break;
		case ArmatureLinker.CharacterType.MIXAMO:
			faceRenderersParams = faceRenderersParams_Mixamo;
			break;
		case ArmatureLinker.CharacterType.CC3:
			_breastL = chest.FindDeepChild ("L_Breast"); //From CC3 default skeleton
			if (_breastL != null) {
				breastL = _breastL;
			}

			_breastR = chest.FindDeepChild ("R_Breast"); //From CC3 default skeleton
			if (_breastR != null) {
				breastR = _breastR;
			}
				
			faceRenderersParams = faceRenderersParams_CC3;
			break;
		case ArmatureLinker.CharacterType.MAKEHUMAN:
		case ArmatureLinker.CharacterType.DEFAULT:
			_breastL = chest.FindDeepChild ("breast.L"); //From makehuman default skeleton
			if (_breastL != null) {
				breastL = _breastL;
			}

			_breastR = chest.FindDeepChild ("breast.R"); //From makehuman default skeleton
			if (_breastR != null) {
				breastR = _breastR;
			}

			if (eyeL != null) {//Must be a makehuman character for this to work.
				var _eyelidL = eyeL.parent.Find ("orbicularis03.L"); //From makehuman default skeleton
				if (_eyelidL != null) {
					eyelidL = _eyelidL;
				}
			}
			if (eyeR != null) {//Must be a makehuman character for this to work.
				var _eyelidR = eyeR.parent.Find ("orbicularis03.R"); //From makehuman default skeleton
				if (_eyelidR != null) {
					eyelidR = _eyelidR;
				}
			}
			faceRenderersParams = faceRenderersParams_MakeHuman;
			break;
		default:
			Debug.LogError ("Non-templateType detected - unable to determine which blendshapes naming to use!");
			return;
		}

		ApplyFaceController (avatarMesh, faceRenderersParams);

	}
	//DAZ facerig (and weights are for vocalizer expressions)
	public static BlendShapeParams[] faceRenderersParams_Daz3D = new BlendShapeParams[] {
	
	};


	//Mixamo facerig (and weights are for vocalizer expressions)
	public static BlendShapeParams[] faceRenderersParams_Mixamo = new BlendShapeParams[] {
		new BlendShapeParams() {shapeName = "BrowsDown_Left", shapeWeight = 2.5f},
		new BlendShapeParams() {shapeName = "BrowsDown_Right", shapeWeight = 2.5f},
	
		new BlendShapeParams() {shapeName = "Squint_Left", shapeWeight = 2.0f},
		new BlendShapeParams() {shapeName = "Squint_Right", shapeWeight = 2.0f},
	
		new BlendShapeParams() {shapeName = "CheekPuff_Left", shapeWeight = 0.8f},
		new BlendShapeParams() {shapeName = "CheekPuff_Right", shapeWeight = 0.8f},
		
		new BlendShapeParams() {shapeName = "Smile_Left",  shapeWeight = 5.0f},
		new BlendShapeParams() {shapeName = "Smile_Right", shapeWeight = 5.0f},
	
		new BlendShapeParams() {shapeName = "MouthWhistle_NarrowAdjust_Left", shapeWeight = 2.0f},
		new BlendShapeParams() {shapeName = "MouthWhistle_NarrowAdjust_Right", shapeWeight = 2.0f},

		new BlendShapeParams() {shapeName = "LowerLipDown_Left", shapeWeight = 2.0f},
		new BlendShapeParams() {shapeName = "LowerLipDown_Right", shapeWeight = 2.0f},
		
		new BlendShapeParams() {shapeName = "UpperLipUp_Left", shapeWeight = 1.0f},
		new BlendShapeParams() {shapeName = "UpperLipUp_Right", shapeWeight = 1.0f},
	};

	//CC3 facerig (and weights are for vocalizer expressions)
	public static BlendShapeParams[] faceRenderersParams_CC3 = new BlendShapeParams[] {
		new BlendShapeParams() {shapeName = "Brow_Drop_L", shapeWeight = 2.5f},
		new BlendShapeParams() {shapeName = "Brow_Drop_R", shapeWeight = 2.5f},
	
		new BlendShapeParams() {shapeName = "Eye_Squint_L", shapeWeight = 2.0f},
		new BlendShapeParams() {shapeName = "Eye_Squint_R", shapeWeight = 2.0f},
	
		new BlendShapeParams() {shapeName = "Cheek_Blow_L", shapeWeight = 0.8f},
		new BlendShapeParams() {shapeName = "Cheek_Blow_R", shapeWeight = 0.8f},
	
		new BlendShapeParams() {shapeName = "Cheek_Raise_L", shapeWeight = 1.0f},
		new BlendShapeParams() {shapeName = "Cheek_Raise_R", shapeWeight = 1.0f},
	
		new BlendShapeParams() {shapeName = "Mouth_Smile_L",  shapeWeight = 5.0f},
		new BlendShapeParams() {shapeName = "Mouth_Smile_R", shapeWeight = 5.0f},
	
		new BlendShapeParams() {shapeName = "Lip_Open", shapeWeight = 7.5f},
		new BlendShapeParams() {shapeName = "Mouth_Top_Lip_Up", shapeWeight = 5.0f},
	};
	
	
	
	//MakeHuman facerig (and weights are for vocalizer expressions)
	public static BlendShapeParams[] faceRenderersParams_MakeHuman = new BlendShapeParams[] {
		new BlendShapeParams() {shapeName = "brow_mid_down_left",    shapeWeight = 2.5f},
		new BlendShapeParams() {shapeName = "brow_mid_down_right",   shapeWeight = 2.5f},
	
		new BlendShapeParams() {shapeName = "cheek_squint_left",     shapeWeight = 2.0f},
		new BlendShapeParams() {shapeName = "cheek_squint_right",    shapeWeight = 2.0f},
	
		new BlendShapeParams() {shapeName = "cheek_balloon_left",    shapeWeight = 0.8f},
		new BlendShapeParams() {shapeName = "cheek_balloon_right",   shapeWeight = 0.8f},
	
		new BlendShapeParams() {shapeName = "cheek_up_left",         shapeWeight = 1.0f},
		new BlendShapeParams() {shapeName = "cheek_up_right",        shapeWeight = 1.0f},
	
		new BlendShapeParams() {shapeName = "mouth_corner_in_left",  shapeWeight = 1.0f},
		new BlendShapeParams() {shapeName = "mouth_corner_in_right", shapeWeight = 1.0f},
	
		new BlendShapeParams() {shapeName = "mouth_corner_up_left",  shapeWeight = 5.0f},
		new BlendShapeParams() {shapeName = "mouth_corner_up_right", shapeWeight = 5.0f},
	
		new BlendShapeParams() {shapeName = "mouth_wide_left",       shapeWeight = 15.0f},
		new BlendShapeParams() {shapeName = "mouth_wide_right",      shapeWeight = 15.0f},
	
		new BlendShapeParams() {shapeName = "lips_part",             shapeWeight = 7.5f},
		new BlendShapeParams() {shapeName = "lips_upper_in",         shapeWeight = 5.0f},
	};


	public void ApplyFaceController(GameObject armatureMesh, BlendShapeParams[] faceRenderersParams) {
		//iterate through all blendshapes in each mesh until a mesh with all blendshapes is found that match the BlendShapeParams array from the template (which is the mesh for face renderer)
		foreach (Transform t in armatureMesh.transform) {
			SkinnedMeshRenderer mesh = t.GetComponent<SkinnedMeshRenderer> ();
			if (mesh == null) {
				continue;
			}

			bool state = mesh.sharedMesh.blendShapeCount > 0;
			foreach (BlendShapeParams blendShape in faceRenderersParams) {
				state = state && (mesh.sharedMesh.GetBlendShapeIndex (blendShape.shapeName) != -1);	
				//Debug.Log("STATE " + state + " --- " + blendShape.shapeName);
				if (!state) {
					break;
				}
			}	
			if (state == true) { //if all blendshapes were present
				faceRenderer = mesh;
				break;
			}
		}
	}



}
