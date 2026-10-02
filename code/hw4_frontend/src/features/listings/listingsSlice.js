import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { api } from "../../api/axios";

const message = (error, fallback) => error.response?.data?.detail || `${fallback}: ${error.message}`;
export const fetchListings = createAsyncThunk("listings/fetch", async (_, thunkAPI) => {
  try { return (await api.get("/listings?skip=0&limit=200")).data; }
  catch (error) { return thunkAPI.rejectWithValue(message(error, "Could not load listings")); }
});
export const createListing = createAsyncThunk("listings/create", async (payload, thunkAPI) => {
  try { return (await api.post("/listings", payload)).data; }
  catch (error) { return thunkAPI.rejectWithValue(message(error, "Could not create listing")); }
});
export const updateListing = createAsyncThunk("listings/update", async ({ id, payload }, thunkAPI) => {
  try { return (await api.put(`/listings/${id}`, payload)).data; }
  catch (error) { return thunkAPI.rejectWithValue(message(error, "Could not update listing")); }
});
export const deleteListing = createAsyncThunk("listings/delete", async (id, thunkAPI) => {
  try { await api.delete(`/listings/${id}`); return id; }
  catch (error) { return thunkAPI.rejectWithValue(message(error, "Could not delete listing")); }
});

const slice = createSlice({
  name: "listings",
  initialState: { items: [], loading: false, error: null },
  reducers: {},
  extraReducers: (builder) => builder
    .addCase(fetchListings.pending, (state) => { state.loading = true; state.error = null; })
    .addCase(fetchListings.fulfilled, (state, action) => { state.loading = false; state.items = action.payload; })
    .addCase(fetchListings.rejected, (state, action) => { state.loading = false; state.error = action.payload; })
    .addCase(createListing.fulfilled, (state, action) => { state.items.push(action.payload); })
    .addCase(createListing.rejected, (state, action) => { state.error = action.payload; })
    .addCase(updateListing.fulfilled, (state, action) => { const index = state.items.findIndex((item) => item.id === action.payload.id); if (index >= 0) state.items[index] = action.payload; })
    .addCase(updateListing.rejected, (state, action) => { state.error = action.payload; })
    .addCase(deleteListing.fulfilled, (state, action) => { state.items = state.items.filter((item) => item.id !== action.payload); })
    .addCase(deleteListing.rejected, (state, action) => { state.error = action.payload; }),
});

export default slice.reducer;
