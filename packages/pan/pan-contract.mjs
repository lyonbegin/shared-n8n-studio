/**
 * Shared official n8n Vue Flow pan/selection behavior contract.
 * Contains no business logic, secrets, or custom execution engine.
 */
export const CANVAS_PAN = Object.freeze({
  panButtons: Object.freeze([0, 1]),
  marqueeModifier: 'Shift',
  activationModifiers: Object.freeze([' ', 'Control']),
  pointerTarget: 'pane',
});
