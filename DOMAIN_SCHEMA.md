# Rental Housing Listing Domain Schema

## Entity

**RentalHousingListing** represents a residential property advertised for rent.

## Fields

| Field | HTML name | Type | Required | Description |
|---|---|---|---|---|
| Property title (primary) | `propertyTitle` | String | Yes | A short name that identifies the rental listing. |
| Property location (secondary) | `propertyLocation` | String | Yes | The street address, neighborhood, or city of the property. |
| Submitter email | `submitterEmail` | Email string | Yes | Contact email of the person submitting the listing. |
| Property description (content) | `propertyDescription` | String | Yes | Details about the property; must contain more than 25 characters. |
| Property category | `propertyCategory` | Enum string | Yes | The type of rental property. |
| Terms accepted | `termsAccepted` | Boolean-like string | Yes | Records agreement to the terms and conditions. |
| Submission date | `submissionDate` | ISO 8601 date-time string | Added by JavaScript | Date and time added after a valid submission. |

## Category Values

The `propertyCategory` field accepts exactly these four domain-appropriate values:

1. `Apartment`
2. `House`
3. `Condo`
4. `Townhouse`

## Validation Rules

- `propertyTitle`, `propertyLocation`, `submitterEmail`, and `propertyDescription` cannot be empty.
- `submitterEmail` must have a valid email format.
- `propertyDescription`, after surrounding whitespace is removed, must contain more than 25 characters.
- The terms-and-conditions checkbox must be selected before submission.
