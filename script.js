const exprEl = document.getElementById('expression');
const resultEl = document.getElementById('result');
const copyBtn = document.getElementById('copyResult');
const keypadModeBtn = document.getElementById('keypadMode');
const nlModeBtn = document.getElementById('nlMode');
const keypadPanel = document.getElementById('keypad');
const nlPanel = document.getElementById('nlPrompt');
const nlInput = document.getElementById('nlInput');
const nlSubmit = document.getElementById('nlSubmit');
const themeToggle = document.getElementById('themeToggle');
const historyList = document.getElementById('historyList');
const clearHistoryBtn = document.getElementById('clearHistory');
const exportHistoryBtn = document.getElementById('exportHistory');
const breakdownContent = document.getElementById('breakdownContent');
const quickChips = document.getElementById('quickChips');

let expression = '';
let result = '';
let history = [];

// MathJS shortcut
const math = window.math;

// Keypad layout
const keypadLayout = [
['(', ')', '^', 'sqrt'],
['sin', 'cos', 'tan', 'log'],
['ln', 'π', 'e', '÷'],
['7', '8', '9', '×'],
['4', '5', '6', '-'],
['1', '2', '3', '+'],
['0', '.', '⌫', '='],
['C']
];

function buildKeypad() {
keypadPanel.innerHTML = '';
keypadLayout.forEach(row => {
row.forEach(label => {
const btn = document.createElement('button');
btn.textContent = label;
btn.dataset.label = label;
btn.addEventListener('click', () => handleKeypadBtn(label));
keypadPanel.appendChild(btn);
});
});
}

function handleKeypadBtn(label) {
switch(label) {
case 'C': expression = ''; result = ''; updateDisplay(); break;
case '⌫': expression = expression.slice(0, -1); updateDisplay(); break;
case '=': calculate(); break;
case 'π': expression += 'pi'; break;
case 'e': expression += 'e'; break;
case '÷': expression += '/'; break;
case '×': expression += '*'; break;
default: expression += label; updateDisplay();
}
}

function updateDisplay() {
exprEl.textContent = expression || '&nbsp;';
resultEl.textContent = result || '&nbsp;';
}

function calculate() {
if (!expression) return;
try {
const res = math.evaluate(expression);
result = res.toString();
exprEl.textContent = expression;
resultEl.textContent = result;
addToHistory(expression, result, 'Arithmetic', '');
expression = '';
} catch (e) {
result = 'Error';
resultEl.textContent = result;
}
}

copyBtn.addEventListener('click', () => {
if (result) {
navigator.clipboard.writeText(result).then(() => {
copyBtn.textContent = 'Copied!';
setTimeout(() => copyBtn.textContent = 'Copy', 1500);
});
}
});

// Natural Language processing
function parseNL(text) {
text = text.trim().toLowerCase();
let steps = '';
let val = null;
let type = 'General';

// Split bill with tip
const billMatch = text.match(/split a\s*\$?([\d,.]+)\s*bill\s+between\s+(\d+)\s+people\s+with\s+(\d+)%\s*tip/);
if (billMatch) {
const amount = parseFloat(billMatch[1].replace(/,/g, ''));
const people = parseInt(billMatch[2]);
const tipPercent = parseFloat(billMatch[3]);
const tip = amount * (tipPercent/100);
const total = amount + tip;
const perPerson = total / people;
val = perPerson;
steps = `Bill amount: $${amount.toFixed(2)}
Tip (${tipPercent}%): $${tip.toFixed(2)}
Total with tip: $${total.toFixed(2)}
Split among ${people} people: $${perPerson.toFixed(2)} each`;
type = 'Finance';
return {val, steps, type};
}

// Compound interest
const ciMatch = text.match(/calculate\s+([\d.]+)\s+years?\s+of\s+compound\s+interest\s+on\s*\$?([\d,.]+)\s+at\s+([\d.]+)%\s+annual/);
if (ciMatch) {
const years = parseFloat(ciMatch[1]);
const principal = parseFloat(ciMatch[2].replace(/,/g, ''));
const rate = parseFloat(ciMatch[3])/100;
// assume yearly compounding
const future = principal * Math.pow(1 + rate, years);
const interest = future - principal;
val = future;
steps = `Principal: $${principal.toFixed(2)}
Annual rate: ${(rate*100).toFixed(2)}%
Years: ${years}
Future value: $${future.toFixed(2)}
Interest earned: $${interest.toFixed(2)}`;
type = 'Finance';
return {val, steps, type};
}

// Simple unit conversion (length)
const convMatch = text.match(/convert\s+([\d.]+)\s*([a-zA-Z]+)\s+to\s+([a-zA-Z]+)/);
if (convMatch) {
const value = parseFloat(convMatch[1]);
const from = convMatch[2].toLowerCase();
const to = convMatch[3].toLowerCase();
const factors = { mm:0.001, cm:0.01, m:1, km:1000, in:0.0254, ft:0.3048, yd:0.9144, mi:1609.34 };
if (factors[from] && factors[to]) {
const meters = value * factors[from];
const result = meters / factors[to];
val = result;
steps = `${value} ${from} = ${meters.toFixed(4)} m
${meters.toFixed(4)} m = ${result.toFixed(4)} ${to}`;
type = 'Conversion';
return {val, steps, type};
}
}

// Fallback: try to evaluate as math expression
try {
val = math.evaluate(text);
steps = `Expression: ${text}
Result: ${val}`;
type = 'Arithmetic';
return {val, steps, type};
} catch (_) {
return {val: null, steps: 'Could not understand the request.', type: 'Error'};
}
}

nlSubmit.addEventListener('click', () => {
const query = nlInput.value.trim();
if (!query) return;
const {val, steps, type} = parseNL(query);
if (val !== null) {
result = val.toString();
exprEl.textContent = query;
resultEl.textContent = result;
breakdownContent.textContent = steps;
addToHistory(query, result, type, steps);
} else {
result = 'Error';
resultEl.textContent = result;
breakdownContent.textContent = steps;
addToHistory(query, result, type, steps);
}
nlInput.value = '';
});

// Quick chips
quickChips.addEventListener('click', e => {
if (e.target.classList.contains('chip')) {
const chip = e.target.textContent.toLowerCase();
let placeholder = '';
if (chip === 'finance') placeholder = 'e.g., Split a $142 bill between 4 people with an 18% tip';
else if (chip === 'conversions') placeholder = 'e.g., Convert 5 miles to km';
else if (chip === 'algebra') placeholder = 'e.g., Solve 2x + 5 = 15';
else if (chip === 'geometry') placeholder = 'e.g., Area of circle with radius 3';
nlInput.placeholder = placeholder;
}
});

// History
function addToHistory(query, res, type, breakdown) {
const entry = {timestamp: new Date(), query, result: res, type, breakdown};
history.push(entry);
renderHistory();
}

function renderHistory() {
historyList.innerHTML = '';
history.slice().reverse().forEach((entry, idx) => {
const li = document.createElement('li');
li.textContent = `[${entry.timestamp.toLocaleTimeString()}] ${entry.query} → ${entry.result}`;
li.dataset.index = history.length - 1 - idx;
li.addEventListener('click', () => {
const i = Number(li.dataset.index);
const entry = history[i];
exprEl.textContent = entry.query;
resultEl.textContent = entry.result;
breakdownContent.textContent = entry.breakdown;
});
historyList.appendChild(li);
});
}

clearHistoryBtn.addEventListener('click', () => {
if (confirm('Clear history?')) {
history = [];
renderHistory();
breakdownContent.textContent = '';
}
});

exportHistoryBtn.addEventListener('click', () => {
if (history.length === 0) { alert('No history to export'); return; }
let csv = 'Timestamp,Query,Result,Type,Breakdown\n';
history.forEach(e => {
const line = [e.timestamp.toISOString(), `"${e.query.replace(/"/g, '""')}"`, `"${e.result}"`, e.type, `"${e.breakdown.replace(/"/g, '""')}"`].join(',');
csv += line + '\n';
});
const blob = new Blob([csv], {type: 'text/csv'});
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = 'calculator_history.csv';
a.click();
URL.revokeObjectURL(url);
});

// Theme toggle
themeToggle.addEventListener('click', () => {
document.body.classList.toggle('dark');
});

// Mode switching
keypadModeBtn.addEventListener('click', () => {
keypadModeBtn.classList.add('active');
nlModeBtn.classList.remove('active');
keypadPanel.classList.add('active');
nlPanel.classList.remove('active');
});
nlModeBtn.addEventListener('click', () => {
nlModeBtn.classList.add('active');
keypadModeBtn.classList.remove('active');
nlPanel.classList.add('active');
keypadPanel.classList.remove('active');
});

// Initial build
buildKeypad();
updateDisplay();
</script>