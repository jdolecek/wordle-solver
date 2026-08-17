const MARKS = ["gray", "yellow", "green"];
const MARK_CHARS = ["B", "Y", "G"];
const STORAGE_KEY = "wordle-solver-game-v1";
const DICTIONARY_KEY = "wordle-solver-dictionary-v1";
const START_WORD_KEY = "level-12-start-word-v1";
const DICTIONARY_META = {
  nyt: {
    label: "NYT 3,209",
    description: "Modern NYT coverage with editor-aware deep search. Previously used answers remain available as a safety net.",
    start: "Begin with SALET using 3,209 modern likely answers.",
  },
  original: {
    label: "Original 2,315",
    description: "Original public solution list. This is the only dictionary with the exact Level 12 guarantee.",
    start: "Begin with SALET and follow the provably optimal Level 12 tree.",
  },
  broad: {
    label: "Broad 14,855",
    description: "Every accepted NYT guess is treated as a possible answer. Safest coverage, but slower and less targeted.",
    start: "Begin with SALET using every accepted word as a possible answer.",
  },
};
const ROOT_ALTERNATIVES = {
  original: ["raise", "slate", "crate", "irate", "trace"],
  nyt: ["tarse", "tiare", "sater", "roate", "raise"],
  broad: ["tares", "lares", "rales", "rates", "ranes"],
};
const STRATEGY_STATS = [
  { level: 5, name: "Greedy information", min: 2, average: 3.45788, max: 5, counts: [82, 1156, 1012, 65] },
  { level: 10, name: "Risk-averse minimax", min: 2, average: 3.47862, max: 5, counts: [83, 1106, 1061, 65] },
  { level: 11, name: "Expected turns", min: 2, average: 3.46782, max: 5, counts: [83, 1128, 1042, 62] },
  { level: 12, name: "Provably optimal", min: 2, average: 3.42117, max: 5, counts: [78, 1225, 971, 41] },
];

const els = {};
let dictionaries = {};
let answers = [];
let acceptedGuesses = [];
let policy = new Map();
let editorPolicy = new Map();
let methodComparisons = {};
let dictionaryOpenings = {};
let selectedDictionary = "nyt";
let selectedStartWord = "salet";
let state = freshState();

function freshState(dictionary = selectedDictionary, startWord = selectedStartWord) {
  const opener = dictionary === "original" ? "salet" : startWord;
  return {
    dictionary, startWord: opener, history: [], optimal: dictionary === "original",
    editorAware: dictionary === "nyt" && opener === "salet", selectedGuess: null,
    selectedRecommendation: null, feedback: [0, 0, 0, 0, 0],
  };
}

window.addEventListener("DOMContentLoaded", async () => {
  Object.assign(els, {
    loading: document.getElementById("loading"),
    startMenu: document.getElementById("start-menu"),
    startSetup: document.getElementById("start-setup"),
    game: document.getElementById("game"),
    startNew: document.getElementById("start-new"),
    beginNewGame: document.getElementById("begin-new-game"),
    startSetupBack: document.getElementById("start-setup-back"),
    continueGame: document.getElementById("continue-game"),
    continueDescription: document.getElementById("continue-description"),
    dictionaryChoice: document.getElementById("dictionary-choice"),
    dictionaryDescription: document.getElementById("dictionary-description"),
    startWord: document.getElementById("start-word"),
    startWordNote: document.getElementById("start-word-note"),
    startNewDescription: document.getElementById("start-new-description"),
    resumeExisting: document.getElementById("resume-existing"),
    showStats: document.getElementById("show-stats"),
    stats: document.getElementById("stats"),
    statsList: document.getElementById("stats-list"),
    statsBack: document.getElementById("stats-back"),
    knownWord: document.getElementById("known-word"),
    compareWord: document.getElementById("compare-word"),
    comparisonMessage: document.getElementById("comparison-message"),
    comparisonResults: document.getElementById("comparison-results"),
    comparisonWord: document.getElementById("comparison-word"),
    comparisonBest: document.getElementById("comparison-best"),
    comparisonList: document.getElementById("comparison-list"),
    candidateCount: document.getElementById("candidate-count"),
    candidateLabel: document.getElementById("candidate-label"),
    activeDictionary: document.getElementById("active-dictionary"),
    history: document.getElementById("history"),
    recommendations: document.getElementById("recommendations"),
    strategyLabel: document.getElementById("strategy-label"),
    choiceList: document.getElementById("choice-list"),
    customWord: document.getElementById("custom-word"),
    useCustom: document.getElementById("use-custom"),
    feedbackPanel: document.getElementById("feedback-panel"),
    feedbackTitle: document.getElementById("feedback-title"),
    feedbackTiles: document.getElementById("feedback-tiles"),
    submitFeedback: document.getElementById("submit-feedback"),
    changeGuess: document.getElementById("change-guess"),
    solvedPanel: document.getElementById("solved-panel"),
    solvedTitle: document.getElementById("solved-title"),
    accuracyScore: document.getElementById("accuracy-score"),
    accuracyDetail: document.getElementById("accuracy-detail"),
    accuracyBar: document.getElementById("accuracy-bar"),
    message: document.getElementById("message"),
    undo: document.getElementById("undo"),
    newGame: document.getElementById("new-game"),
    playAgain: document.getElementById("play-again"),
    backToMenu: document.getElementById("back-to-menu"),
  });
  bindEvents();
  try {
    selectedDictionary = localStorage.getItem(DICTIONARY_KEY) || "nyt";
    if (!DICTIONARY_META[selectedDictionary]) selectedDictionary = "nyt";
    selectedStartWord = (localStorage.getItem(START_WORD_KEY) || "salet").toLowerCase();
    if (!/^[a-z]{5}$/.test(selectedStartWord)) selectedStartWord = "salet";
    const [answerText, nytAnswerText, guessText, treeText, editorTreeText, comparisonData, openingData] = await Promise.all([
      fetch("data/solutions.txt").then(requireOk).then(r => r.text()),
      fetch("data/nyt_wordlebot_answers.txt").then(requireOk).then(r => r.text()),
      fetch("data/nyt_accepted_guesses.txt").then(requireOk).then(r => r.text()),
      fetch("data/optimal_strategy.txt").then(requireOk).then(r => r.text()),
      fetch("data/editor_strategy.txt").then(requireOk).then(r => r.text()),
      fetch("data/method_comparisons.json").then(requireOk).then(r => r.json()),
      fetch("data/dictionary_openings.json").then(requireOk).then(r => r.json()),
    ]);
    const originalAnswers = answerText.trim().split(/\s+/).map(w => w.toLowerCase());
    const nytAnswers = nytAnswerText.trim().split(/\s+/).map(w => w.toLowerCase());
    acceptedGuesses = guessText.trim().split(/\s+/).map(w => w.toLowerCase());
    dictionaries = { original: originalAnswers, nyt: nytAnswers, broad: acceptedGuesses };
    policy = parseOptimalTree(treeText);
    editorPolicy = parseOptimalTree(editorTreeText);
    methodComparisons = comparisonData;
    dictionaryOpenings = openingData;
    restoreState();
    els.loading.hidden = true;
    showStartMenu();
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("service-worker.js").then(registration => registration.update());
    }
  } catch (error) {
    els.loading.innerHTML = `<p>Could not load the solver. Check your connection and refresh.</p>`;
    console.error(error);
  }
});

function requireOk(response) {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response;
}

function bindEvents() {
  els.useCustom.addEventListener("click", useCustomGuess);
  els.customWord.addEventListener("keydown", event => { if (event.key === "Enter") useCustomGuess(); });
  els.customWord.addEventListener("input", () => { els.customWord.value = els.customWord.value.replace(/[^a-z]/gi, "").slice(0, 5); });
  els.submitFeedback.addEventListener("click", submitFeedback);
  els.changeGuess.addEventListener("click", () => {
    state.selectedGuess = null;
    state.selectedRecommendation = null;
    state.optimal = historyFollowsPolicy(state.history);
    state.editorAware = historyFollowsEditorPolicy(state.history);
    saveState();
    render();
  });
  els.undo.addEventListener("click", undoGuess);
  els.newGame.addEventListener("click", confirmNewGame);
  els.playAgain.addEventListener("click", resetGame);
  els.startNew.addEventListener("click", showNewGameSetup);
  els.beginNewGame.addEventListener("click", startNewGame);
  els.startSetupBack.addEventListener("click", showStartMenu);
  els.continueGame.addEventListener("click", continueSavedGame);
  els.resumeExisting.addEventListener("click", startExistingPuzzle);
  els.dictionaryChoice.addEventListener("change", selectDictionary);
  els.startWord.addEventListener("input", editStartWord);
  els.startWord.addEventListener("blur", validateStartWord);
  els.showStats.addEventListener("click", showStrategyStats);
  els.statsBack.addEventListener("click", showStartMenu);
  els.compareWord.addEventListener("click", compareKnownWord);
  els.knownWord.addEventListener("keydown", event => { if (event.key === "Enter") compareKnownWord(); });
  els.knownWord.addEventListener("input", () => {
    els.knownWord.value = els.knownWord.value.replace(/[^a-z]/gi, "").slice(0, 5);
    els.comparisonMessage.textContent = "";
  });
  els.backToMenu.addEventListener("click", showStartMenu);
}

function parseOptimalTree(text) {
  const result = new Map();
  const guesses = [];
  const feedbacks = [];
  for (const line of text.split(/\r?\n/)) {
    for (let depth = 0; depth < Math.ceil(line.length / 13); depth++) {
      const segment = line.slice(depth * 13, (depth + 1) * 13).padEnd(13);
      const word = segment.slice(0, 5).trim().toLowerCase();
      const feedback = segment.slice(6, 11);
      if (word) { guesses.splice(depth, Infinity, word); feedbacks.splice(depth); }
      if (feedback.trim()) {
        feedbacks.splice(depth, Infinity, feedback);
        const key = feedbacks.slice(0, depth).join("|");
        if (!result.has(key)) result.set(key, guesses[depth]);
      }
    }
  }
  return result;
}

function feedbackFor(guess, answer) {
  const marks = [0, 0, 0, 0, 0];
  const remaining = new Map();
  for (let i = 0; i < 5; i++) {
    if (guess[i] === answer[i]) marks[i] = 2;
    else remaining.set(answer[i], (remaining.get(answer[i]) || 0) + 1);
  }
  for (let i = 0; i < 5; i++) {
    if (marks[i] === 0 && (remaining.get(guess[i]) || 0) > 0) {
      marks[i] = 1;
      remaining.set(guess[i], remaining.get(guess[i]) - 1);
    }
  }
  return marks;
}

function feedbackCode(guess, answer) {
  let greenMask = 0;
  for (let index = 0; index < 5; index++) {
    if (guess[index] === answer[index]) greenMask |= 1 << index;
  }
  let yellowMask = 0, code = 0, factor = 1;
  for (let index = 0; index < 5; index++) {
    let mark = 0;
    if (greenMask & (1 << index)) {
      mark = 2;
    } else {
      let available = 0, alreadyUsed = 0;
      for (let answerIndex = 0; answerIndex < 5; answerIndex++) {
        if (!(greenMask & (1 << answerIndex)) && answer[answerIndex] === guess[index]) available++;
      }
      for (let earlier = 0; earlier < index; earlier++) {
        if ((yellowMask & (1 << earlier)) && guess[earlier] === guess[index]) alreadyUsed++;
      }
      if (alreadyUsed < available) {
        mark = 1;
        yellowMask |= 1 << index;
      }
    }
    code += mark * factor;
    factor *= 3;
  }
  return code;
}

function markKey(marks) { return marks.map(mark => MARK_CHARS[mark]).join(""); }

function currentCandidates() {
  return answers.filter(answer => state.history.every(item => markKey(feedbackFor(item.guess, answer)) === item.feedback));
}

function recommendation(candidates) {
  if (state.optimal) {
    const key = state.history.map(item => item.feedback).join("|");
    const exact = policy.get(key);
    if (exact) {
      // Avoid blocking the first mobile paint with hundreds of thousands of
      // feedback calculations. These are the verified Level 5 opening ranks.
      const alternatives = state.history.length === 0
        ? ROOT_ALTERNATIVES.original
        : rankedLevel5(candidates, 6).filter(w => w !== exact).slice(0, 5);
      return { primary: exact, alternatives, exact: true };
    }
    state.optimal = false;
  }
  if (state.editorAware) {
    const key = state.history.map(item => item.feedback).join("|");
    const editorChoice = editorPolicy.get(key);
    if (editorChoice) {
      const alternatives = state.history.length === 0
        ? ROOT_ALTERNATIVES.nyt
        : rankedLevel5(candidates, 6).filter(word => word !== editorChoice).slice(0, 5);
      return { primary: editorChoice, alternatives, exact: false, editorAware: true };
    }
    state.editorAware = false;
  }
  if (state.history.length === 0) {
    const opener = state.startWord || "salet";
    const alternatives = ["salet", ...ROOT_ALTERNATIVES[state.dictionary]]
      .filter((word, index, words) => word !== opener && words.indexOf(word) === index)
      .slice(0, 5);
    return { primary: opener, alternatives, exact: false };
  }
  if (state.history.length === 1 && state.history[0].guess === "salet") {
    const ranked = dictionaryOpenings[state.dictionary]?.[state.history[0].feedback];
    if (ranked) return { primary: ranked[0], alternatives: ranked.slice(1, 6), exact: false };
  }
  const ranked = rankedLevel5(candidates, 6);
  return { primary: ranked[0], alternatives: ranked.slice(1, 6), exact: false };
}

function rankedLevel5(candidates, limit) {
  if (candidates.length === 1) return [candidates[0]];
  let pool;
  if (state.dictionary === "original") {
    pool = candidates.length > 500
      ? heuristicPool(candidates, 300, dictionaries.original)
      : dictionaries.original;
  } else {
    const shortlisted = heuristicPool(candidates, 40, acceptedGuesses);
    pool = candidates.length <= 60 ? [...new Set([...shortlisted, ...candidates])] : shortlisted;
  }
  const candidateSet = new Set(candidates);
  const scored = pool.map(word => {
    const groups = new Map();
    for (const answer of candidates) {
      const key = feedbackCode(word, answer);
      groups.set(key, (groups.get(key) || 0) + 1);
    }
    let entropy = 0, expected = 0, worst = 0;
    for (const size of groups.values()) {
      const p = size / candidates.length;
      entropy += p * Math.log2(candidates.length / size);
      expected += size * size / candidates.length;
      worst = Math.max(worst, size);
    }
    return { word, entropy, expected, worst, candidate: candidateSet.has(word) };
  });
  scored.sort((a, b) => b.entropy - a.entropy || a.worst - b.worst || a.expected - b.expected || Number(b.candidate) - Number(a.candidate) || a.word.localeCompare(b.word));
  return scored.slice(0, limit).map(item => item.word);
}

function heuristicPool(candidates, limit, source) {
  const letters = new Map(), positions = new Map();
  for (const word of candidates) {
    for (const letter of new Set(word)) letters.set(letter, (letters.get(letter) || 0) + 1);
    for (let i = 0; i < 5; i++) {
      const key = `${i}${word[i]}`;
      positions.set(key, (positions.get(key) || 0) + 1);
    }
  }
  return source.map(word => {
    let score = 0;
    for (const letter of new Set(word)) score += letters.get(letter) || 0;
    for (let i = 0; i < 5; i++) score += .35 * (positions.get(`${i}${word[i]}`) || 0);
    return { word, score };
  }).sort((a, b) => b.score - a.score || a.word.localeCompare(b.word)).slice(0, limit).map(item => item.word);
}

function render() {
  clearMessage();
  const candidates = currentCandidates();
  const solved = state.history.at(-1)?.feedback === "GGGGG";
  els.candidateCount.textContent = solved
    ? state.history.at(-1).guess.toUpperCase()
    : candidates.length.toLocaleString();
  els.candidateLabel.textContent = solved
    ? "solved answer"
    : candidates.length === 1 ? "possible answer" : "possible answers";
  els.activeDictionary.textContent = DICTIONARY_META[state.dictionary].label;
  renderHistory();
  els.undo.disabled = state.history.length === 0;

  els.solvedPanel.hidden = !solved;
  els.recommendations.hidden = solved || Boolean(state.selectedGuess);
  els.feedbackPanel.hidden = solved || !state.selectedGuess;
  if (solved) {
    els.solvedTitle.textContent = `Solved in ${state.history.length} guess${state.history.length === 1 ? "" : "es"}!`;
    renderAccuracy();
    saveState();
    return;
  }
  if (!candidates.length) {
    showMessage("No answers match this history. Undo the last guess and check its colors.");
    els.recommendations.hidden = true;
    els.feedbackPanel.hidden = true;
    return;
  }
  if (state.selectedGuess) renderFeedback();
  else renderChoices(recommendation(candidates));
  saveState();
}

function renderAccuracy() {
  const recorded = state.history.filter(item => typeof item.recommended === "string");
  if (!recorded.length) {
    els.accuracyScore.textContent = "—";
    els.accuracyDetail.textContent = "Accuracy tracking begins with your next game.";
    els.accuracyBar.style.width = "0%";
    return;
  }
  const followed = recorded.filter(item => item.guess === item.recommended).length;
  const accuracy = Math.round(followed / recorded.length * 100);
  els.accuracyScore.textContent = `${accuracy}%`;
  els.accuracyDetail.textContent = `${followed} of ${recorded.length} recorded #1 recommendation${recorded.length === 1 ? "" : "s"} followed`;
  els.accuracyBar.style.width = `${accuracy}%`;
}

function renderHistory() {
  els.history.innerHTML = "";
  for (const item of state.history) {
    const row = document.createElement("div"); row.className = "history-row";
    [...item.guess].forEach((letter, i) => row.append(tile(letter, MARK_CHARS.indexOf(item.feedback[i]), false)));
    els.history.append(row);
  }
}

function renderChoices(choice) {
  els.strategyLabel.textContent = choice.exact
    ? "PROVABLY OPTIMAL"
    : choice.editorAware ? "EDITOR-AWARE · DEEP SEARCH" : "LEVEL 5 · FLEXIBLE";
  const words = [choice.primary, ...choice.alternatives];
  els.choiceList.innerHTML = "";
  words.forEach((word, index) => {
    const button = document.createElement("button"); button.type = "button"; button.className = "choice-button";
    const note = index === 0 && choice.exact ? "exact" : index === 0 && choice.editorAware ? "deep" : "info";
    button.innerHTML = `<span class="choice-rank">${index + 1}</span><span class="choice-word">${word.toUpperCase()}</span><span class="choice-note">${note}</span>`;
    button.addEventListener("click", () => selectGuess(word, choice.primary));
    els.choiceList.append(button);
  });
}

function selectGuess(word, recommended) {
  state.selectedGuess = word.toLowerCase();
  state.selectedRecommendation = recommended.toLowerCase();
  state.feedback = [0, 0, 0, 0, 0];
  if (word !== recommended) state.optimal = false;
  if (word !== recommended) state.editorAware = false;
  saveState(); render();
}

function useCustomGuess() {
  const word = els.customWord.value.trim().toLowerCase();
  if (!/^[a-z]{5}$/.test(word)) return showMessage("Enter exactly five letters.");
  const candidates = currentCandidates();
  const primary = recommendation(candidates).primary;
  els.customWord.value = "";
  selectGuess(word, primary);
}

function renderFeedback() {
  els.feedbackTitle.textContent = `Feedback for ${state.selectedGuess.toUpperCase()}`;
  els.feedbackTiles.innerHTML = "";
  [...state.selectedGuess].forEach((letter, index) => {
    const element = tile(letter, state.feedback[index], true);
    element.setAttribute("aria-label", `${letter.toUpperCase()}: ${MARKS[state.feedback[index]]}`);
    element.addEventListener("click", () => { state.feedback[index] = (state.feedback[index] + 1) % 3; saveState(); renderFeedback(); });
    els.feedbackTiles.append(element);
  });
}

function tile(letter, mark, interactive) {
  const element = document.createElement(interactive ? "button" : "div");
  if (interactive) element.type = "button";
  element.className = `tile ${MARKS[mark]}`;
  element.textContent = letter;
  return element;
}

function submitFeedback() {
  const feedback = markKey(state.feedback);
  const proposed = [...state.history, {
    guess: state.selectedGuess, feedback, recommended: state.selectedRecommendation,
  }];
  const remaining = answers.filter(answer => proposed.every(item => markKey(feedbackFor(item.guess, answer)) === item.feedback));
  if (!remaining.length && feedback !== "GGGGG") return showMessage("Those colors conflict with the earlier guesses. Check the tiles and try again.");
  state.history = proposed;
  state.selectedGuess = null;
  state.selectedRecommendation = null;
  state.feedback = [0, 0, 0, 0, 0];
  saveState(); render();
}

function undoGuess() {
  if (!state.history.length) return;
  state.history.pop();
  state.selectedGuess = null;
  state.selectedRecommendation = null;
  state.feedback = [0, 0, 0, 0, 0];
  state.optimal = historyFollowsPolicy(state.history);
  state.editorAware = historyFollowsEditorPolicy(state.history);
  saveState(); render();
}

function historyFollowsPolicy(history) {
  if (state.dictionary !== "original") return false;
  const feedbacks = [];
  for (const item of history) {
    if (policy.get(feedbacks.join("|")) !== item.guess) return false;
    feedbacks.push(item.feedback);
  }
  return true;
}
function historyFollowsEditorPolicy(history) {
  if (state.dictionary !== "nyt" || state.startWord !== "salet") return false;
  const feedbacks = [];
  for (const item of history) {
    if (editorPolicy.get(feedbacks.join("|")) !== item.guess) return false;
    feedbacks.push(item.feedback);
  }
  return editorPolicy.has(feedbacks.join("|"));
}

function confirmNewGame() {
  showStartMenu();
}
function showStartMenu() {
  els.game.hidden = true;
  els.stats.hidden = true;
  els.startSetup.hidden = true;
  els.startMenu.hidden = false;
  els.dictionaryChoice.value = selectedDictionary;
  updateDictionaryCopy();
  const hasSavedGame = state.history.length > 0 || Boolean(state.selectedGuess);
  els.continueGame.disabled = !hasSavedGame;
  els.continueDescription.textContent = hasSavedGame
    ? `Continue after ${state.history.length} completed guess${state.history.length === 1 ? "" : "es"} with ${DICTIONARY_META[state.dictionary].label}.`
    : "No saved puzzle yet.";
}
function selectDictionary() {
  selectedDictionary = els.dictionaryChoice.value;
  localStorage.setItem(DICTIONARY_KEY, selectedDictionary);
  updateDictionaryCopy();
}
function editStartWord() {
  els.startWord.value = els.startWord.value.replace(/[^a-z]/gi, "").slice(0, 5).toUpperCase();
  els.startWordNote.classList.remove("input-error");
  if (els.startWord.value.length === 5) validateStartWord();
}
function validateStartWord() {
  if (selectedDictionary === "original") return "salet";
  const word = els.startWord.value.trim().toLowerCase();
  if (!/^[a-z]{5}$/.test(word)) {
    els.startWordNote.textContent = "Enter exactly five letters.";
    els.startWordNote.classList.add("input-error");
    return null;
  }
  if (!acceptedGuesses.includes(word)) {
    els.startWordNote.textContent = "That word is not in Wordle's accepted guess list.";
    els.startWordNote.classList.add("input-error");
    return null;
  }
  selectedStartWord = word;
  localStorage.setItem(START_WORD_KEY, selectedStartWord);
  els.startWordNote.textContent = word === "salet" && selectedDictionary === "nyt"
    ? "SALET enables the editor-aware deep-search strategy."
    : word === "salet"
      ? "SALET is the recommended default, or enter any accepted five-letter word."
    : `${word.toUpperCase()} will be the solver's first recommendation.`;
  els.startWordNote.classList.remove("input-error");
  updateStartDescription(word);
  return word;
}
function updateDictionaryCopy() {
  const meta = DICTIONARY_META[selectedDictionary];
  els.dictionaryDescription.textContent = meta.description;
  const exact = selectedDictionary === "original";
  els.startWord.disabled = exact;
  els.startWord.value = (exact ? "salet" : selectedStartWord).toUpperCase();
  els.startWordNote.textContent = exact
    ? "The exact Level 12 strategy is proven specifically for SALET."
    : selectedStartWord === "salet" && selectedDictionary === "nyt"
      ? "SALET enables the editor-aware deep-search strategy."
      : selectedStartWord === "salet"
      ? "SALET is the recommended default, or enter any accepted five-letter word."
      : `${selectedStartWord.toUpperCase()} will be the solver's first recommendation.`;
  els.startWordNote.classList.remove("input-error");
  updateStartDescription(exact ? "salet" : selectedStartWord);
}
function updateStartDescription(word) {
  if (selectedDictionary === "original") {
    els.startNewDescription.textContent = DICTIONARY_META.original.start;
    return;
  }
  if (selectedDictionary === "nyt") {
    els.startNewDescription.textContent = word === "salet"
      ? "Start with SALET and use the editor-aware deep-search strategy."
      : `Start with ${word.toUpperCase()}, then continue with the flexible strategy.`;
    return;
  }
  els.startNewDescription.textContent = "Choose your opening word, then begin with the flexible strategy.";
}
function applyDictionary(dictionary) {
  const active = dictionaries[dictionary] ? dictionary : "nyt";
  state.dictionary = active;
  if (active === "original") state.startWord = "salet";
  answers = dictionaries[active];
  if (active !== "original") state.optimal = false;
  if (active !== "nyt") state.editorAware = false;
}
function openGame() {
  applyDictionary(state.dictionary);
  els.startMenu.hidden = true;
  els.startSetup.hidden = true;
  els.stats.hidden = true;
  els.game.hidden = false;
  render();
}
function showStrategyStats() {
  els.startMenu.hidden = true;
  els.startSetup.hidden = true;
  els.game.hidden = true;
  els.stats.hidden = false;
  els.knownWord.focus();
  renderOverallStats();
}
function renderOverallStats() {
  const bestAverage = Math.min(...STRATEGY_STATS.map(item => item.average));
  els.statsList.innerHTML = "";
  for (const item of STRATEGY_STATS) {
    const total = item.counts.reduce((sum, count) => sum + count, 0);
    const card = document.createElement("article");
    card.className = `stats-card${item.average === bestAverage ? " best" : ""}`;
    const bars = item.counts.map(count => `<span style="width:${(count / total * 100).toFixed(3)}%"></span>`).join("");
    const distribution = item.counts.map((count, index) => `${index + 2}: ${count.toLocaleString()}`).join(" · ");
    card.innerHTML = `
      <div class="stats-card-head">
        <span class="stats-name"><strong>Level ${item.level}</strong><small>${item.name}</small></span>
        <span class="stat-number">${item.min}</span>
        <span class="stat-number average">${item.average.toFixed(2)}</span>
        <span class="stat-number">${item.max}</span>
      </div>
      <div class="distribution" aria-hidden="true">${bars}</div>
      <p class="distribution-label">Guesses — ${distribution}</p>`;
    els.statsList.append(card);
  }
}
function compareKnownWord() {
  const word = els.knownWord.value.trim().toLowerCase();
  els.comparisonMessage.textContent = "";
  if (!/^[a-z]{5}$/.test(word)) {
    els.comparisonResults.hidden = true;
    els.comparisonMessage.textContent = "Enter exactly five letters.";
    return;
  }
  const paths = methodComparisons[word];
  if (!paths) {
    els.comparisonResults.hidden = true;
    els.comparisonMessage.textContent = "That word is not in the 2,315-answer comparison set.";
    return;
  }
  const bestScore = Math.min(...paths.map(path => path.length));
  const winners = STRATEGY_STATS.filter((_, index) => paths[index].length === bestScore).map(item => `Level ${item.level}`);
  els.comparisonWord.textContent = word.toUpperCase();
  els.comparisonBest.textContent = `${winners.join(", ")} ${winners.length === 1 ? "wins" : "tie"} at ${bestScore} guess${bestScore === 1 ? "" : "es"}`;
  els.comparisonList.innerHTML = "";
  STRATEGY_STATS.forEach((item, index) => {
    const path = paths[index];
    const card = document.createElement("article");
    card.className = `comparison-card${path.length === bestScore ? " best" : ""}`;
    const guessPath = path.map((guess, guessIndex) =>
      `${guessIndex ? '<span class="path-arrow">→</span>' : ""}<span class="path-word">${guess.toUpperCase()}</span>`
    ).join("");
    card.innerHTML = `
      <div class="comparison-card-head">
        <span class="stats-name"><strong>Level ${item.level}</strong><small>${item.name}</small></span>
        <span class="comparison-score">${path.length} guess${path.length === 1 ? "" : "es"}</span>
      </div>
      <div class="guess-path">${guessPath}</div>`;
    els.comparisonList.append(card);
  });
  els.comparisonResults.hidden = false;
}
function startNewGame() {
  const startWord = validateStartWord();
  if (!startWord) { els.startWord.focus(); return; }
  if ((state.history.length || state.selectedGuess) && !window.confirm("Erase the saved puzzle and start over?")) return;
  state = freshState(selectedDictionary, startWord);
  saveState();
  openGame();
}
function showNewGameSetup() {
  if (selectedDictionary === "original") {
    startNewGame();
    return;
  }
  updateDictionaryCopy();
  els.startMenu.hidden = true;
  els.stats.hidden = true;
  els.game.hidden = true;
  els.startSetup.hidden = false;
  els.startWord.focus();
  els.startWord.select();
}
function continueSavedGame() { openGame(); }
function startExistingPuzzle() {
  if ((state.history.length || state.selectedGuess) && !window.confirm("Erase the saved puzzle and enter a different one?")) return;
  state = freshState(selectedDictionary, "salet");
  saveState();
  openGame();
  showMessage("Enter the first word you already played, then match its tile colors.");
  els.customWord.focus();
}
function resetGame() {
  const dictionary = state.dictionary;
  const startWord = state.startWord || "salet";
  state = freshState(dictionary, startWord);
  saveState(); openGame();
}
function showMessage(text) { els.message.textContent = text; }
function clearMessage() { els.message.textContent = ""; }
function saveState() { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
function restoreState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved && Array.isArray(saved.history)) {
      const dictionary = DICTIONARY_META[saved.dictionary] ? saved.dictionary : "original";
      const startWord = dictionary === "original" ? "salet" : saved.startWord || "salet";
      state = { ...freshState(dictionary, startWord), ...saved, dictionary, startWord };
      if (typeof saved.editorAware !== "boolean") {
        state.editorAware = historyFollowsEditorPolicy(state.history);
      }
    } else {
      state = freshState(selectedDictionary);
    }
  } catch { localStorage.removeItem(STORAGE_KEY); }
}
