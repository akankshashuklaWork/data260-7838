const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const repositoryRoot = path.resolve(root, "..", "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "script.js"), "utf8");
const schema = fs.readFileSync(path.join(repositoryRoot, "DOMAIN_SCHEMA.md"), "utf8");

let failures = 0;

const test = (name, condition) => {
  if (condition) {
    console.log(`PASS: ${name}`);
  } else {
    failures += 1;
    console.error(`FAIL: ${name}`);
  }
};

test("page title is HW1-Akanksha", /<title>HW1-Akanksha<\/title>/.test(html));
test("largest heading tag names the entity", /<h1[^>]*>Rental Housing Listing<\/h1>/.test(html));
test("primary text input is required and autofocus", /id="propertyTitle"[\s\S]*?autofocus[\s\S]*?required/.test(html));
test("secondary input is required", /id="propertyLocation"[\s\S]*?required/.test(html));
test("submitter email uses email type", /type="email"[\s\S]*?name="submitterEmail"/.test(html));
test("description is a required textarea", /<textarea[\s\S]*?name="propertyDescription"[\s\S]*?required/.test(html));
test("category dropdown has four selectable options", (html.match(/<option value="(Apartment|House|Condo|Townhouse)">/g) || []).length === 4);
test("terms label has required wording", html.includes("I agree to the terms and conditions."));
test("script is linked at the end of body", /<script src="script\.js"><\/script>\s*<\/body>/.test(html));
test("description validation requires more than 25 characters", script.includes("description.length <= 25"));
test("terms checkbox is validated", script.includes("!termsCheckbox.checked"));
test("form data is converted to a JSON string", script.includes("JSON.stringify(formObject)"));
test("JSON string is parsed", script.includes("JSON.parse(jsonString)"));
test("object destructuring extracts title and email", script.includes("const { propertyTitle, submitterEmail }"));
test("spread operator adds submissionDate", /\.\.\.parsedObject,[\s\S]*?submissionDate: new Date\(\)\.toISOString\(\)/.test(script));
test(
  "submission counter uses a closure",
  /const createSubmissionCounter = \(\) => \{[\s\S]*?let count = 0;[\s\S]*?return \(\) =>/.test(script) ||
    /const submissionCounter = \(\(\) => \{[\s\S]*?let count = 0;[\s\S]*?return \(\) =>[\s\S]*?\}\)\(\)/.test(script)
);
test("schema defines the entity fields", schema.includes("RentalHousingListing") && schema.includes("## Category Values"));
test("strict mode is enabled", /^(?:\s*\/\/[^\n]*\n)*\s*"use strict";/.test(script));
test("regular and arrow functions are demonstrated", /function getTrimmedValue\(/.test(script) && /const validateForm = \(\) =>/.test(script));
test("Promise and async-await are demonstrated", /new Promise\(/.test(script) && /async \(event\)/.test(script) && /await saveListingToServer/.test(script));
test("successful submissions are added to the page", html.includes('id="listingSubmissions"') && /document\.createElement\("li"\)/.test(script));
test("delete handler uses bind", /handleDelete\.bind\(null, submissionId\)/.test(script));

try {
  new vm.Script(script);
  test("JavaScript parses without syntax errors", true);
} catch (error) {
  console.error(error);
  test("JavaScript parses without syntax errors", false);
}

if (failures > 0) {
  console.error(`\n${failures} test(s) failed.`);
  process.exit(1);
}

console.log("\nAll assignment checks passed.");
