using System.Collections;
using System.Collections.Generic;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;

public class BuildAvatar : MonoBehaviour {

	void UpdateMyFormatedName (string assetBundleName) {
		string formatName = "MoCapRig_{0}HumanoidTpose";

		string prefabName = string.Format(formatName, assetBundleName);

		transform.name = prefabName;

		var linker = GetComponentInChildren<ArmatureLinker> ();
		if (linker != null) {
			linker.defaultModel = assetBundleName.ToLower();
		}
	}

	public void CreateEmptyContianers(string modelAssetName, ArmatureLinker.CharacterType characterType) {

		GameObject metarig = null;
		GameObject avatarMesh = null;

		gameObject.SetActive (true);

		if (!transform.Find("skinned_mesh")) {
			avatarMesh = new GameObject ();

			//var avatarMesh = model.AddComponent<GameObject> ();
			avatarMesh.name = "skinned_mesh";
			avatarMesh.transform.parent = transform;

			List<Transform> allChildren = new List<Transform>();
			for (int i = 0; i < transform.childCount; i++) {
				var child = transform.GetChild (i);
				allChildren.Add (child);
			}

			string rootBoneName;

			switch (characterType) {
			case ArmatureLinker.CharacterType.REALLUSION:
				rootBoneName = "cc_base_boneroot";
				break;
			case ArmatureLinker.CharacterType.MAKEHUMAN:
			case ArmatureLinker.CharacterType.DEFAULT:
				rootBoneName = "root";
				break;
			default:
				Debug.LogError ("Non-templateType detected - unable to determine what to use for root bone naming!");
				return;
			}

			foreach (Transform child in allChildren) {
				
				if (child.GetComponent<SkinnedMeshRenderer> ()) {
					child.transform.parent = avatarMesh.transform;
				} else {


					if (child.childCount > 0 && child.GetChild (0).name.ToLower ().Equals (rootBoneName)) {//cc_base_boneroot")) {
						metarig = child.gameObject;//.GetChild (0).gameObject;// child.gameObject;

						//metarig.transform.parent = transform;
						//GameObject.DestroyImmediate (child.gameObject);
					}
				}

			}

		}

		var linker = GetComponentInChildren<ArmatureLinker> ();

		if (metarig != null) {
			if (linker == null) {
				linker = metarig.AddComponent<ArmatureLinker> ();

				SetLayerRecursively (linker.gameObject, LayerMask.NameToLayer ("Default"));
			}
		}

		if (avatarMesh != null) {
			if (transform.Find ("skinned_mesh") == null) {
				Transform t = new GameObject ("skinned_mesh").transform;
				t.parent = transform;
				t.localPosition = Vector3.zero;
				t.localRotation = Quaternion.identity;

				avatarMesh.transform.parent = t;
			}
		}

		UpdateMyFormatedName (modelAssetName);

		linker.PopulateFields (avatarMesh, characterType);
	}


	public static void SetLayerRecursively(GameObject go, int layerNumber)
	{
		foreach (Transform trans in go.GetComponentsInChildren<Transform>(true))
		{
			trans.gameObject.layer = layerNumber;
		}
	}

}
#endif