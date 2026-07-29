export const baselineRows = [
  { name: "Equal weight", return: 14.97, sharpe: 1.766 },
  { name: "SAC", return: 13.83, sharpe: 1.802 },
  { name: "TD3", return: 13.22, sharpe: 1.73 },
  { name: "Risk parity", return: 12.84, sharpe: 1.756 },
  { name: "PPO", return: 12.12, sharpe: 1.69 },
  { name: "Mean variance", return: 8.78, sharpe: null },
  { name: "Buy & hold", return: 7.33, sharpe: null },
  { name: "Cash", return: 0, sharpe: null },
];

export const transferRows = [
  { name: "Joint market", return: 11.94, sharpe: 1.894 },
  { name: "To US", return: 4.85, sharpe: 1.243 },
  { name: "To CN", return: 4.08, sharpe: 1.149 },
  { name: "Leave-one-market-out", return: 3.02, sharpe: 1.044 },
  { name: "To JP", return: 2.53, sharpe: 0.799 },
  { name: "Single market", return: 2.4, sharpe: 1.035 },
  { name: "To HK", return: 0.63, sharpe: 0.987 },
  { name: "Unseen stock", return: 0.54, sharpe: 0.406 },
];

export const agentRows = [
  { name: "No LLM", return: 5.86, sharpe: 1.953 },
  { name: "Research", return: 5.86, sharpe: 1.953 },
  { name: "Hierarchical", return: 4.68, sharpe: 1.952 },
  { name: "Risk", return: 0.43, sharpe: 0.391 },
  { name: "Research + risk", return: 0.32, sharpe: 0.816 },
  { name: "Full stack / committee", return: 0, sharpe: 0 },
];

export const hpoRows = [
  { name: "Random", score: 1.879 },
  { name: "CMA-ES", score: 1.76 },
  { name: "Genetic", score: 1.644 },
  { name: "NSGA-II", score: 1.615 },
  { name: "Differential evolution", score: 1.608 },
  { name: "Default", score: 1.569 },
  { name: "TPE", score: 1.558 },
  { name: "PSO", score: 1.204 },
];
