using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;


public class ArmatureFaceController : MonoBehaviour {

	[Header("Face Blendshapes")]
	public SkinnedMeshRenderer faceRenderer; //the renderer that has the eyelid blend shapes

	//This is a MakeHuman default facerig (and weights are for default female like expressions), may be overridden during character creation by the BuildMakehumanCharacter script
	public ArmatureLinker.BlendShapeParams[] faceRenderersParams /*= new BlendShapeParams[]{};*/ = new ArmatureLinker.BlendShapeParams[] {
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

	[Range (1,5000)]
	public int blendshapeWeight = 788; //the multiplier for eyelids

	[Header("Jaw Bone Movement")]


	public Vector3 moveDirection = Vector3.forward; //the local direction (and amplitude) to move the jaw (as average freq shifts)
	public Vector3 rotateDirection = Vector3.right; //the local rotation axis (and amplitude) to rotate the jaw around

	[Range (1,100)]
	public float jawRotateRate = 35; //the rate the jaw opens/closes as amplitude changes

	[Range (1,100)]
	public float jawMoveRate = 15; //the rate the jaw moves as average frequency shifts

	[Header("Eyelid Movement")]
	public Vector3 eyeLidCloseDirection;

	[Range (1,50)]
	public int eyelidWeight = 10; //the multiplier for eyelids


}
