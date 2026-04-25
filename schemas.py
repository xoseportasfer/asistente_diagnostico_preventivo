from pydantic import BaseModel


# What the frontend sends to us
class TicketRequest(BaseModel):
    customer_name: str
    customer_email: str
    ticket_subject: str
    ticket_message: str


# What we send back to the frontend
class TicketResponse(BaseModel):
    customer_name: str
    customer_email: str
    category: str
    complexity: str
    urgency: str
    path_taken: str
    resolution_subject: str
    resolution_message: str
    follow_up_needed: bool
