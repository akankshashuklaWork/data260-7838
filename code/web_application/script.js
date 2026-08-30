// ===== CONCEPT 1: STRICT MODE =====
// Strict mode catches some common JavaScript mistakes and uses safer parsing rules.
"use strict";

// ===== CONCEPT 2: REGULAR FUNCTION =====
// This traditional function reads a form field and removes surrounding spaces.
// getElementById finds an HTML element, value gets the typed text, and trim removes extra spaces.
function getTrimmedValue(fieldId) {
  return document.getElementById(fieldId).value.trim();
}

// ===== CONCEPT 3: CLOSURE =====
// A closure lets the returned arrow function remember the private count variable.
// The surrounding function runs immediately, but count stays available for future submissions.
const submissionCounter = (() => {
  let count = 0;
  return () => ++count;
})();

// ===== CONCEPT 4: DOM REFERENCES =====
// Saving frequently used page elements in constants makes the remaining code easier to read.
const form = document.getElementById("rentalListingForm");
const descriptionField = document.getElementById("propertyDescription");
const termsCheckbox = document.getElementById("termsAccepted");
const characterCount = document.getElementById("characterCount");
const formStatus = document.getElementById("formStatus");
const submissionsList = document.getElementById("listingSubmissions");

// ===== CONCEPT 5: ARROW FUNCTION AND CUSTOM VALIDATION =====
// An arrow function is a shorter modern way to write a function.
// This function returns false when a custom rule fails and true when both rules pass.
const validateForm = () => {
  const description = descriptionField.value.trim();

  // The assignment requires the description to contain more than 25 characters.
  if (description.length <= 25) {
    alert("The property description must contain more than 25 characters.");
    descriptionField.focus();
    return false;
  }

  // The assignment also requires the terms checkbox to be checked.
  if (!termsCheckbox.checked) {
    alert("Please agree to the terms and conditions before submitting.");
    termsCheckbox.focus();
    return false;
  }

  return true;
};

// ===== CONCEPT 6: PROMISE =====
// A Promise represents work that finishes later. This simulates saving to a server.
// setTimeout creates a short delay, and resolve marks the simulated save as successful.
const saveListingToServer = (listingData) => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(`Listing "${listingData.propertyTitle}" saved successfully.`);
    }, 500);
  });
};

// ===== CONCEPT 7: DELETE HANDLER =====
// This regular function removes a selected submission from the displayed list.
const handleDelete = function (submissionId) {
  const submission = document.getElementById(submissionId);
  if (submission) {
    console.log(`Deleting submission: ${submissionId}`);
    submission.remove();
  }

  // If every item was deleted, restore a helpful empty-list message.
  if (submissionsList.children.length === 0) {
    const emptyState = document.createElement("li");
    emptyState.id = "emptyState";
    emptyState.className = "empty-state";
    emptyState.textContent = "No listings submitted yet.";
    submissionsList.appendChild(emptyState);
  }
};

// ===== CONCEPT 8: CREATE HTML WITH JAVASCRIPT =====
// createElement builds new page elements, and appendChild places them into the document.
const addListingToUI = (listingData) => {
  document.getElementById("emptyState")?.remove();

  // Destructuring extracts the properties needed to display one submission.
  const { propertyTitle, propertyLocation, propertyCategory, submissionId } = listingData;
  const listItem = document.createElement("li");
  listItem.setAttribute("id", submissionId);

  const listingText = document.createElement("span");
  listingText.textContent = `${propertyTitle} — ${propertyCategory}, ${propertyLocation}`;

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "delete-button";
  deleteButton.textContent = "Delete";
  // bind creates a new handler that remembers which submission ID should be deleted.
  deleteButton.onclick = handleDelete.bind(null, submissionId);

  listItem.appendChild(listingText);
  listItem.appendChild(deleteButton);
  submissionsList.appendChild(listItem);
};

// ===== CONCEPT 9: INPUT EVENT LISTENER =====
// The input event runs every time the description changes and updates the character count.
descriptionField.addEventListener("input", () => {
  const length = descriptionField.value.trim().length;
  characterCount.textContent = `${length} ${length === 1 ? "character" : "characters"}`;
});

// ===== CONCEPT 10: ASYNC FORM SUBMISSION =====
// The async keyword allows this event handler to wait for the Promise later in the function.
form.addEventListener("submit", async (event) => {
  // preventDefault stops the browser from reloading the page after submission.
  event.preventDefault();
  formStatus.textContent = "";

  // ===== CONCEPT 11: BUILT-IN AND CUSTOM FORM VALIDATION =====
  // Browser validation checks required inputs and the email format.
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  if (!validateForm()) {
    return;
  }

  // ===== CONCEPT 12: COLLECT FORM DATA =====
  // FormData reads named form controls; Object.fromEntries converts the entries into an object.
  const formData = new FormData(form);
  const formObject = Object.fromEntries(formData.entries());
  formObject.propertyTitle = getTrimmedValue("propertyTitle");
  formObject.propertyLocation = getTrimmedValue("propertyLocation");
  formObject.submitterEmail = getTrimmedValue("submitterEmail");
  formObject.propertyDescription = getTrimmedValue("propertyDescription");

  // ===== CONCEPT 13: JSON OPERATIONS =====
  // JSON.stringify converts a JavaScript object into a JSON string.
  const jsonString = JSON.stringify(formObject);
  console.log("Form data as JSON:", jsonString);

  // JSON.parse converts the JSON string back into a JavaScript object.
  const parsedObject = JSON.parse(jsonString);
  console.log("Parsed form data:", parsedObject);

  // ===== CONCEPT 14: OBJECT DESTRUCTURING =====
  // Destructuring extracts the assignment's primary field and email field.
  const { propertyTitle, submitterEmail } = parsedObject;
  console.log("Primary field (property title):", propertyTitle);
  console.log("Submitter email:", submitterEmail);

  const submissionCount = submissionCounter();

  // ===== CONCEPT 15: SPREAD OPERATOR =====
  // Three dots copy all parsed properties before adding the required submission date.
  const updatedParsedObject = {
    ...parsedObject,
    submissionDate: new Date().toISOString(),
    submissionId: `listing-${submissionCount}`
  };
  console.log("Updated parsed object:", updatedParsedObject);
  console.log("Successful submission count:", submissionCount);

  // ===== CONCEPT 16: ASYNC/AWAIT AND ERROR HANDLING =====
  // await pauses this handler until the Promise succeeds; try/catch handles possible errors.
  try {
    formStatus.textContent = "Saving listing...";
    const serverResponse = await saveListingToServer(updatedParsedObject);
    console.log(serverResponse);
    addListingToUI(updatedParsedObject);
    formStatus.textContent = `Listing submitted successfully. Submission #${submissionCount}`;
    // reset clears the form, then focus returns the cursor to the primary field.
    form.reset();
    characterCount.textContent = "0 characters";
    document.getElementById("propertyTitle").focus();
  } catch (error) {
    console.error("Unable to save the listing:", error);
    alert("The listing could not be saved. Please try again.");
  }
});
