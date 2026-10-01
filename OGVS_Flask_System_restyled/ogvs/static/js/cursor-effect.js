(() => {
  const supportsSparkles = window.matchMedia(
    '(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)'
  );

  if (!supportsSparkles.matches) {
    return;
  }

  let lastSparkleTime = 0;

  window.addEventListener('pointermove', (pointerEvent) => {
    const currentTime = performance.now();
    if (pointerEvent.pointerType !== 'mouse' || currentTime - lastSparkleTime < 55) {
      return;
    }

    lastSparkleTime = currentTime;
    const sparkle = document.createElement('span');
    sparkle.className = 'sparkle';
    sparkle.style.left = `${pointerEvent.clientX}px`;
    sparkle.style.top = `${pointerEvent.clientY}px`;
    sparkle.addEventListener('animationend', () => sparkle.remove(), { once: true });
    document.body.append(sparkle);
    window.setTimeout(() => sparkle.remove(), 650);
  }, { passive: true });
})();