"""Question sets used by HW10.

EVAL_QUESTIONS   - the 20 questions whose Writer drafts become the frozen judge-validation cases.
                   They mix routine questions, questions about the six listings in the HW9
                   database (the ingress hands those facts to the Writer), and a few vague,
                   unanswerable, or off-topic ones so that real drafts differ in quality.
LATENCY_QUESTIONS - 50 distinct questions for the cache-miss latency experiment. They are checked
                   against each other (and against an emptied cache) so none can be a cache hit.
"""

from __future__ import annotations

EVAL_QUESTIONS: list[str] = [
    # Routine rental questions
    "What should a renter check before signing a lease for a two-bedroom apartment in San Jose?",
    "How much security deposit can a landlord legally ask for in California?",
    "How can I tell whether a rental listing is a scam?",
    "What is the difference between a fixed-term lease and a month-to-month rental agreement?",
    "Can my landlord raise the rent in the middle of a lease?",
    "What should I do if my landlord does not return my security deposit?",
    "Is a pet deposit normally refundable?",
    "What questions should I ask a landlord during a viewing?",
    # Questions about the six listings in the database (the Writer receives the record's facts)
    "What are the monthly rent and the pet policy at Maple Court?",
    "How much is the security deposit at Cedar Heights, and what type of property is it?",
    "Can I keep a dog at Willow Lane?",
    "Is Birch Street more expensive per month than Harbor View?",
    "What are the monthly rent and the location of Pine Ridge?",
    # Vague, unanswerable, or off-topic questions
    "Is the place any good?",
    "What is the monthly rent at Oak Meadows?",
    "Write a short poem about the stock market.",
    "What is the exact square footage of Harbor View?",
    "Will rents in San Jose go up next year?",
    "Do I need renters insurance and how much does it cost?",
    "Summarize a tenant's rights in Texas in one sentence.",
]

LATENCY_QUESTIONS: list[str] = [
    "How is a rental application fee calculated, and can it be refunded?",
    "What does joint and several liability mean for roommates on one lease?",
    "How many days of notice must a landlord give before entering my apartment?",
    "What happens if I break my lease early in California?",
    "Who normally pays for water, gas, and electricity in an apartment lease?",
    "When is subletting my apartment allowed?",
    "How can I verify that the person advertising a rental really owns the building?",
    "Do studios usually require a smaller security deposit than larger units?",
    "What is a rent-controlled unit and how do I find out whether mine is covered?",
    "How should I document the condition of an apartment on move-in day?",
    "Are landlords required to provide air conditioning in California?",
    "What is a co-signer and when does a landlord ask for one?",
    "How long can a landlord keep my deposit after I move out?",
    "What fees are commonly hidden in rental listings besides the rent?",
    "Is renters insurance required by law, or only by some landlords?",
    "How do I ask a landlord to repair a broken heater?",
    "What is the typical length of a residential lease in Silicon Valley?",
    "Can a landlord refuse to rent to someone because they have a service animal?",
    "What credit score do most landlords expect from applicants?",
    "How do I read the utilities section of a lease agreement?",
    "What should I know about parking rules when renting a townhouse?",
    "How is a prorated first month of rent calculated?",
    "What can I do if my neighbors are constantly noisy?",
    "How do landlords usually verify an applicant's income?",
    "Is it legal for a landlord to change the locks without notice?",
    "What is the difference between a condo and an apartment for a tenant?",
    "How much notice must I give before I move out of a month-to-month rental?",
    "What does normal wear and tear mean when a deposit is returned?",
    "How do I handle a landlord who sells the building while I live there?",
    "What are the pros and cons of renting a house instead of an apartment?",
    "Is Cedar Heights a good choice for someone who works from home?",
    "Does Willow Lane allow both dogs and cats?",
    "What would I pay up front to move into Pine Ridge?",
    "How does the rent at Birch Street compare with the deposit there?",
    "Which listing in Oakland would suit a student on a small budget?",
    "What documents should I bring to a rental application appointment?",
    "How do I negotiate a lower rent with a private landlord?",
    "What is an estoppel certificate and why might a tenant sign one?",
    "How can I spot mold problems before I rent a unit?",
    "Do landlords have to allow me to paint the walls?",
    "What are common reasons a rental application gets rejected?",
    "How do I get my deposit back if my roommate moves out early?",
    "What is the purpose of a move-out inspection?",
    "Can a landlord charge a late fee of any amount they like?",
    "How do I find out whether a building has had pest problems?",
    "What does a lease clause about guests and occupancy limits usually say?",
    "How should I plan my budget so rent stays under one third of my income?",
    "What internet and cable arrangements are typical in apartment buildings?",
    "What are my options if the landlord refuses to renew my lease?",
    "How do shared-wall noise rules differ between a duplex and a high-rise?",
]
