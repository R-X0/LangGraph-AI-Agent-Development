from neo4j import GraphDatabase

class GraphDB:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_job_posting(self, job_data):
        with self.driver.session() as session:
            session.execute_write(self._create_job_posting, job_data)

    @staticmethod
    def _create_job_posting(tx, job_data):
        query = (
            "CREATE (j:JobPosting {title: $title, company: $company, location: $location, description: $description, postDate: $postDate})"
        )
        tx.run(query, title=job_data['job_title'], company=job_data['company_name'],
               location=job_data['job_location'], description=job_data['job_description'],
               postDate=job_data['job_post_date'])

    def create_company_contact(self, company_name, contact_info):
        with self.driver.session() as session:
            session.execute_write(self._create_company_contact, company_name, contact_info)

    @staticmethod
    def _create_company_contact(tx, company_name, contact_info):
        query = (
            "MERGE (c:Company {name: $company_name}) "
            "SET c.contactInfo = $contact_info"
        )
        tx.run(query, company_name=company_name, contact_info=contact_info)