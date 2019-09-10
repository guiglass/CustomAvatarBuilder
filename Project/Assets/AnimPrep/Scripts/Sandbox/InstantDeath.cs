using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class InstantDeath : SandboxBase {
	
	public Transform enableOnTouch;
	public float disableAfterSeconds = 10;

	public float delayTime = 0.075f; //a short delay so the charcter can really make contact (then when being animated, the character should make good contact to the collider causing the explosion to be more likely to occur during playback)
	protected override void Awake() {
		base.Awake ();
		if (enableOnTouch) {
			enableOnTouch.gameObject.SetActive (false);
		}
	}

	private void OnTriggerEnter(Collider other)
	{
		StartCoroutine (OnTriggerEnterRoutine (other));
	}

	IEnumerator OnTriggerEnterRoutine(Collider other)
	{
		yield return new WaitForSeconds (delayTime);
		/*if (!VaptureRecorder.Instance.isPlaying) {			
			var ragdoll = other.transform.GetComponentInParent<Ragdoll>();
			if (ragdoll) {
				ragdoll.transform.parent.GetComponentInChildren<Armature> ().KillPuppet ();
			}
		}*/

		if (enableOnTouch) {
			enableOnTouch.gameObject.SetActive (false);
			enableOnTouch.gameObject.SetActive (true);

			if (disableObjectRoutine != null) {
				StopCoroutine (disableObjectRoutine);
			}
			disableObjectRoutine = StartCoroutine (DisableObjectRoutine ());

			var m_audio = enableOnTouch.GetComponentInChildren<AudioSource> ();
			if (m_audio) {
				m_audio.Play ();
			}
		}
	}

	Coroutine disableObjectRoutine;
	IEnumerator DisableObjectRoutine() {
		yield return new WaitForSeconds (disableAfterSeconds);
		if (enableOnTouch) {
			enableOnTouch.gameObject.SetActive (false);
		}
		disableObjectRoutine = null;
	}

}
