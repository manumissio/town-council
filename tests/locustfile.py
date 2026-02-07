import random
from locust import HttpUser, task, between

# --------------------------------------------------------------------------
# NOVICE DEVELOPER NOTE:
# This is a "Locust" file. It simulates "Virtual Users" attacking our API.
# You can run it to see how many users the system can handle before it breaks.
# --------------------------------------------------------------------------

class TownCouncilUser(HttpUser):
    """
    Simulates a regular citizen browsing the website.
    They wait between 1 and 3 seconds between actions to feel realistic.
    """
    wait_time = between(1, 3)
    
    # Common headers
    headers = {
        "X-API-Key": "dev_secret_key_change_me"
    }

    @task(5)
    def search_zoning(self):
        """Users search for common topics like 'zoning'"""
        self.client.get("/search?q=zoning&limit=10", headers=self.headers)

    @task(10)
    def get_metadata(self):
        """Users look at the city/org filters (This should be fast due to Redis)"""
        self.client.get("/metadata", headers=self.headers)

    @task(3)
    def view_person_profile(self):
        """Users look at a specific official (Tests Eager Loading efficiency)"""
        # We use a known ID from our test data or a random small integer
        person_id = random.randint(1, 100) 
        self.client.get(f"/person/{person_id}", headers=self.headers)

    @task(1)
    def health_check(self):
        """Simple probe to see if the system is alive"""
        self.client.get("/health")

    def on_start(self):
        """Code that runs when a user first 'wakes up'"""
        print("Starting Virtual User Simulation...")
