"use strict";

const form = document.getElementById("rentalListingForm");
const searchForm = document.getElementById("searchForm");
const descriptionField = document.getElementById("propertyDescription");
const termsCheckbox = document.getElementById("termsAccepted");
const characterCount = document.getElementById("characterCount");
const formStatus = document.getElementById("formStatus");
const submissionsList = document.getElementById("listingSubmissions");
const loadingState = document.getElementById("loadingState");
const errorState = document.getElementById("errorState");
const searchInput = document.getElementById("searchInput");

function getTrimmedValue(fieldId) {
  return document.getElementById(fieldId).value.trim();
}

const submissionCounter = (() => {
  let count = 0;
  return () => ++count;
})();

const validateForm = () => {
  const description = descriptionField.value.trim();
  if (description.length <= 25) {
    alert("The property description must contain more than 25 characters.");
    descriptionField.focus();
    return false;
  }
  if (!termsCheckbox.checked) {
    alert("Please agree to the terms and conditions before submitting.");
    termsCheckbox.focus();
    return false;
  }
  return true;
};

const setStatus = (message, isError = false) => {
  formStatus.textContent = message;
  formStatus.classList.toggle("error-state", isError);
};

const listingFromForm = () => {
  const values = Object.fromEntries(new FormData(form).entries());
  values.propertyTitle = getTrimmedValue("propertyTitle");
  values.propertyLocation = getTrimmedValue("propertyLocation");
  values.submitterEmail = getTrimmedValue("submitterEmail");
  values.propertyDescription = getTrimmedValue("propertyDescription");
  return values;
};

const saveListingToServer = (method, url, listingData) => new Promise((resolve, reject) => {
  fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(listingData),
  }).then((response) => {
    if (!response.ok) throw new Error("The listing could not be saved.");
    resolve(response);
  }).catch(reject);
});

const renderListings = (listings) => {
  submissionsList.innerHTML = "";
  submissionsList.hidden = false;
  if (listings.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No listings match your search.";
    submissionsList.appendChild(empty);
    return;
  }
  listings.forEach((listing) => {
    const item = document.createElement("li");
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = listing.propertyTitle;
    text.append(title, ` — ${listing.propertyCategory}, ${listing.propertyLocation}`);
    const details = document.createElement("small");
    details.textContent = listing.propertyDescription;
    text.append(document.createElement("br"), details);
    const id = document.createElement("span");
    id.textContent = `ID ${listing.id}`;
    item.append(text, id);
    submissionsList.appendChild(item);
  });
};

const fetchListings = async (search = "") => {
  loadingState.hidden = false;
  errorState.hidden = true;
  submissionsList.hidden = true;
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  try {
    const response = await fetch(`/api/listings${query}`);
    if (!response.ok) throw new Error("Request failed");
    renderListings(await response.json());
  } catch (error) {
    console.error(error);
    errorState.hidden = false;
  } finally {
    loadingState.hidden = true;
  }
};

const sendListing = async (method, url, message) => {
  const formObject = listingFromForm();
  const jsonString = JSON.stringify(formObject);
  const parsedObject = JSON.parse(jsonString);
  const { propertyTitle, submitterEmail } = parsedObject;
  console.log("Form data as JSON:", jsonString);
  console.log("Primary field (property title):", propertyTitle);
  console.log("Submitter email:", submitterEmail);
  const submissionCount = submissionCounter();
  const updatedParsedObject = {
    ...parsedObject,
    submissionDate: new Date().toISOString(),
    submissionId: `listing-${submissionCount}`,
  };
  console.log("Updated parsed object:", updatedParsedObject);
  console.log("Successful submission count:", submissionCount);
  await saveListingToServer(method, url, updatedParsedObject);
  window.location.assign("/");
  form.reset();
  characterCount.textContent = "0 characters";
  setStatus(message);
  await fetchListings(searchInput.value.trim());
};

descriptionField.addEventListener("input", () => {
  const length = descriptionField.value.trim().length;
  characterCount.textContent = `${length} ${length === 1 ? "character" : "characters"}`;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.checkValidity() || !validateForm()) {
    form.reportValidity();
    return;
  }
  try {
    setStatus("Saving listing…");
    await sendListing("POST", "/api/listings", "Listing added successfully.");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("updateListing").addEventListener("click", async () => {
  if (!form.checkValidity() || !validateForm()) {
    form.reportValidity();
    return;
  }
  try {
    setStatus("Updating listing ID 1…");
    await sendListing("PUT", "/api/listings/1", "Listing ID 1 updated successfully.");
  } catch (error) {
    setStatus(error.message, true);
  }
});

const handleDelete = async function () {
  try {
    const response = await fetch("/api/listings/highest", { method: "DELETE" });
    if (!response.ok) throw new Error("No listing could be deleted.");
    window.location.assign("/");
  } catch (error) {
    setStatus(error.message, true);
  }
};

const submissionId = "highest";
document.getElementById("deleteHighest").addEventListener("click", handleDelete.bind(null, submissionId));

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  fetchListings(searchInput.value.trim());
});

document.getElementById("clearSearch").addEventListener("click", () => {
  searchInput.value = "";
  fetchListings();
});

fetchListings();
