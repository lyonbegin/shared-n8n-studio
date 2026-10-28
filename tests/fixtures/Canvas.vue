<script setup lang="ts">
const panningKeyCode = ref<string[] | true>(isMobileDevice ? true : [' ', controlKeyCode]);
const panningMouseButton = ref<number[] | true>(isMobileDevice ? true : [1]);
const selectionKeyCode = ref<string | true | null>(isMobileDevice ? 'Shift' : true);
const isInPanningMode = ref(false);
function switchToPanningMode() {
	selectionKeyCode.value = null;
	panningMouseButton.value = [0, 1];
	isInPanningMode.value = true;
}
function switchToSelectionMode() {
	selectionKeyCode.value = true;
	panningMouseButton.value = [1];
	isInPanningMode.value = false;
}
</script>
<template>
<VueFlow :pan-on-drag="panningMouseButton"
  :selection-key-code="selectionKeyCode"
  :pan-activation-key-code="panningKeyCode" />
</template>
