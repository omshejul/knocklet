function appear(reduced: boolean | null, delay = 0) {
  return {
    initial: reduced
      ? { opacity: 0 }
      : { opacity: 0, y: 12, filter: "blur(12px)" },
    animate: reduced
      ? { opacity: 1 }
      : { opacity: 1, y: 0, filter: "blur(0px)" },
    exit: reduced
      ? { opacity: 0 }
      : { opacity: 0, y: 8, filter: "blur(10px)" },
    transition: {
      duration: reduced ? 0.01 : 0.2,
      delay,
      ease: "easeOut" as const,
    },
  };
}

export { appear };
