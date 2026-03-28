(() => {
  const stamp = document.querySelector(".footer small");
  if (!stamp) {
    return;
  }
  stamp.dataset.clientBoot = new Date().toISOString();
})();
