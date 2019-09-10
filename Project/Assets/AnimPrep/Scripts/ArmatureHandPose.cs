using System.Collections;
using System.Collections.Generic;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;

[CustomEditor(typeof(ArmatureHandPose))]
class ArmatureHandPoseEditor : Editor {
	public override void OnInspectorGUI() {

		GUIStyle customLabel;

		EditorGUILayout.Space ();

		customLabel = new GUIStyle ("Label");
		customLabel.alignment = TextAnchor.LowerLeft;
		customLabel.fontSize = 10;
		customLabel.normal.textColor = Color.black;
		customLabel.fontStyle = FontStyle.Italic;
		customLabel.wordWrap = true;
		GUILayout.Label ("Used by the auto-populatate transforms inspector script to indicate that this is the prefered finger orientation template for properly orientating all fingers of this character", customLabel);


		EditorGUILayout.Space ();

		DrawDefaultInspector ();
	}
}
#endif



public class ArmatureHandPose : MonoBehaviour {

	public enum HandSide {
		left,
		right
	}
	[Tooltip("Which hand this template was copied from (determines primary hand)")]
	public HandSide handSide = HandSide.left;

	[Header("_Thumb Targets_")]
	public Transform clinched_target;
	public Transform rest_target;
	public Transform open_target;

	[Header("_Hand_")]
	public Transform hand;
	[Header("_Fingers_")]
	public Transform thumb;
	public Transform index;
	public Transform middle;
	public Transform ring;
	public Transform pinky;

	void OnValidate() { //enforce naming
		if (clinched_target) {
			clinched_target.name = "clinched_target";
		}
		if (rest_target) {
			rest_target.name = "rest_target";
		}
		if (open_target) {
			open_target.name = "open_target";
		}
	}


}
