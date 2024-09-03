# src/linkedinSalesNavigator.py

import time
import re
from playwright.sync_api import expect
from collections import defaultdict
from src.utils.utils import save_data_into_json
from tenacity import retry, stop_after_attempt, wait_fixed

def sanitize_text(text):
    return re.sub(r'[^a-zA-Z0-9\s]', '', text)

class LinkedInSalesNavigator:
    def __init__(self, CONFIGS, page):
        self.CONFIGS = CONFIGS
        self.page = page
        self.base_url = CONFIGS["BaseUrl"]
        self.analyzed_job_posts = []

    def login(self):
        print("-> Logging into LinkedIn")
        self.page.goto(self.base_url)
        self.page.wait_for_timeout(3000)

        if "Login screen" in self.page.content():
            print("-> Login required. Please check your cookies.")
            return False

        print("-> Successfully logged into LinkedIn")
        return True

    def set_filters(self):
        print("\n-> Setting Filters")
        try:
            self.set_company_filters()
            self.set_job_title_filters()
            self.set_seniority_level_filters()
            
            if self.CONFIGS["OnlyUSProspects"]:
                self.set_location_filters()  # This may now raise an exception

            self.page.click('[aria-label="Collapse filter panel"]')
        except Exception as e:
            print(f"Fatal error in setting filters: {str(e)}")
            print("Aborting the automation process due to filter setting failure.")
            raise  # Re-raise the exception to stop the entire process

    def set_company_filters(self):
        print("-> Setting Company Filters")
        for job_post in self.analyzed_job_posts:
            try:
                self.page.wait_for_selector('fieldset [title="Current company"] li-icon[type="plus-icon"]', state="visible")
                self.page.click('fieldset [title="Current company"] li-icon[type="plus-icon"]')
                company_input = self.page.locator('fieldset [title="Current company"] input')
                company_input.wait_for(state="visible")
                
                sanitized_company = sanitize_text(job_post["company_name"])
                company_input.fill(sanitized_company)

                self.page.wait_for_timeout(200)

                options = self.page.locator('ul[role="listbox"] li')
                found = False
                for option in options.all():
                    if sanitized_company.lower() in sanitize_text(option.inner_text()).lower():
                        option.click()
                        found = True
                        break

                if not found:
                    print(f"-> Failed to find Company: {sanitized_company}")
                    if self.CONFIGS["UseFirstOption"]:
                        options.first.click()
                    elif self.CONFIGS["UseSearchQuery"]:
                        company_input.press('Enter')

                # Verify the filter was applied
                applied_filters = self.page.locator('fieldset [title="Current company"] .artdeco-pill')
                if not applied_filters.count():
                    print(f"Warning: Filter for '{sanitized_company}' may not have been applied.")

            except Exception as e:
                print(f"Error setting company filter for '{sanitized_company}': {str(e)}")
                continue

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def set_single_job_title_filter(self, job_title, is_first_entry=False):
        print(f"  -> Setting filter for job title: {job_title}")
        
        # Look for the input field
        title_input = self.page.locator('input[placeholder="Add current titles"]')
        if not title_input.count():
            # If not found, we might need to open the job title filter section
            self.page.click('fieldset [title="Current job title"] li-icon[type="plus-icon"]')
            title_input = self.page.locator('input[placeholder="Add current titles"]')
        
        title_input.wait_for(state="visible")
        
        # Clear the input field
        title_input.fill("")
        
        sanitized_title = sanitize_text(job_title)
        
        # Type out the job title character by character
        for char in sanitized_title:
            title_input.type(char)
            self.page.wait_for_timeout(50)  # Small delay between characters
        
        print(f"  -> Typed job title: {sanitized_title}")
        self.page.wait_for_timeout(100)
        
        if is_first_entry:
            # For the first entry, wait for suggestions and click the first one
            try:
                self.page.wait_for_selector('ul[role="listbox"]', state="visible", timeout=5000)
                self.page.click('ul[role="listbox"] li:first-child')
                print("  -> Clicked first suggestion")
            except Exception as e:
                print(f"  -> No suggestions appeared for first entry. Pressing Enter. Error: {str(e)}")
                title_input.press('Enter')
        else:
            # For subsequent entries, just press Enter
            print("  -> Subsequent entry: Pressing Enter")
            title_input.press('Enter')
        
        # Verify the filter was applied
        self.page.wait_for_timeout(1000)
        applied_filters = self.page.locator('fieldset [title="Current job title"] .artdeco-pill')
        if not applied_filters.count():
            raise Exception(f"Filter for '{sanitized_title}' was not applied.")
        
        print(f"  -> Filter applied successfully for: {sanitized_title}")
        
        # Wait for any animations or UI updates to complete
        self.page.wait_for_timeout(1000)

    def set_job_title_filters(self):
        print("-> Setting Job Title Filters")
        for index, job_title in enumerate(self.CONFIGS["RequiredJobTitles"]):
            try:
                print(f"  -> Attempting to set filter for job title {index + 1}: {job_title}")
                self.set_single_job_title_filter(job_title, is_first_entry=(index == 0))
                print(f"  -> Successfully set filter for job title {index + 1}: {job_title}")
            except Exception as e:
                print(f"Error setting job title filter for '{job_title}': {str(e)}")
            
            # Check if the filter was actually applied
            applied_filters = self.page.locator('fieldset [title="Current job title"] .artdeco-pill')
            applied_count = applied_filters.count()
            print(f"  -> Current number of applied job title filters: {applied_count}")
            
            # Wait for any UI updates
            self.page.wait_for_timeout(1000)
        
        print("-> Finished attempting to set all job title filters")
        # After setting all filters, wait for any final UI updates
        self.page.wait_for_timeout(1000)
        
        # Final verification of all applied filters
        applied_filters = self.page.locator('fieldset [title="Current job title"] .artdeco-pill')
        applied_count = applied_filters.count()
        expected_count = len(self.CONFIGS["RequiredJobTitles"])
        if applied_count != expected_count:
            print(f"Warning: Expected {expected_count} job title filters, but found {applied_count}")
        else:
            print(f"Successfully applied all {applied_count} job title filters")

    def set_seniority_level_filters(self):
        print("-> Setting Seniority Level Filters")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Click to expand the Seniority level filter if it's collapsed
                expand_button = self.page.locator('fieldset[title="Seniority level"] button[aria-expanded="false"]')
                if expand_button.count() > 0:
                    expand_button.click()
                    self.page.wait_for_timeout(1000)

                for index, seniority_level in enumerate(self.CONFIGS["RequiredSeniorityLevels"]):
                    print(f"  -> Setting filter for seniority level: {seniority_level}")
                    
                    # Look for the specific seniority level option
                    option_selector = f'li[aria-label*="{seniority_level}" i]'
                    option = self.page.locator(option_selector)
                    
                    if option.count() > 0:
                        # Click the "Include" button for this seniority level
                        include_button = option.locator('div[aria-label*="Include" i]')
                        if include_button.count() > 0:
                            include_button.click()
                            print(f"  -> Included: {seniority_level}")
                            
                            # Add a longer delay after selecting the first seniority level
                            if index == 0:
                                self.page.wait_for_timeout(2000)  # 2 second delay after the first selection
                            else:
                                self.page.wait_for_timeout(1000)  # 1 second delay for subsequent selections
                        else:
                            print(f"  -> Warning: Include button not found for '{seniority_level}'")
                    else:
                        print(f"  -> Warning: Seniority level '{seniority_level}' not found")

                # Verify the filters were applied
                applied_filters = self.page.locator('fieldset[title="Seniority level"] .artdeco-pill')
                applied_count = applied_filters.count()
                print(f"  -> Applied {applied_count} seniority level filters")

                if applied_count != len(self.CONFIGS["RequiredSeniorityLevels"]):
                    raise Exception(f"Not all seniority level filters were applied. Expected: {len(self.CONFIGS['RequiredSeniorityLevels'])}, Applied: {applied_count}")

                print("  -> All seniority level filters applied successfully")
                return  # Exit the method if successful

            except Exception as e:
                print(f"Error setting seniority level filters (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print("  -> Retrying...")
                    self.page.wait_for_timeout(2000)  # Wait before retrying
                else:
                    print("  -> Max retries reached. Aborting seniority level filter setting.")
                    raise  # Re-raise the exception to stop the entire process

        # Wait for any UI updates
        self.page.wait_for_timeout(1000)

    def set_location_filters(self):
        print("-> Setting Location Filters")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Expand the Geography filter if it's collapsed
                expand_button = self.page.locator('fieldset[title="Geography"] button[aria-expanded="false"]')
                if expand_button.count() > 0:
                    expand_button.click()
                    self.page.wait_for_timeout(1000)

                # Look for the input field
                geography_input = self.page.locator('input[placeholder="Add locations"]')
                if not geography_input.count():
                    # If not found, we might need to open the geography filter section
                    self.page.click('fieldset[title="Geography"] li-icon[type="plus-icon"]')
                    geography_input = self.page.locator('input[placeholder="Add locations"]')
                
                geography_input.wait_for(state="visible")

                # Include United States
                self.type_and_include(geography_input, "United States")
                print("  -> Included: United States")

                # Exclude specified states
                for state in self.CONFIGS["StatesToExclude"]:
                    self.type_and_exclude(geography_input, state)
                    print(f"  -> Excluded: {state}")

                self.page.wait_for_timeout(2000)  # Wait for the UI to update

                # Verify the filters were applied
                applied_filters = self.page.locator('fieldset[title="Geography"] .artdeco-pill')
                applied_count = applied_filters.count()
                expected_count = 1 + len(self.CONFIGS["StatesToExclude"])  # United States + excluded states
                
                if applied_count != expected_count:
                    raise Exception(f"Not all location filters were applied. Expected: {expected_count}, Applied: {applied_count}")

                print(f"  -> Successfully applied {applied_count} location filters")
                return  # Exit the method if successful

            except Exception as e:
                print(f"Error setting location filters (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print("  -> Retrying...")
                    self.page.wait_for_timeout(2000)  # Wait before retrying
                else:
                    print("  -> Max retries reached. Aborting location filter setting.")
                    raise  # Re-raise the exception to stop the entire process

        # Wait for any UI updates
        self.page.wait_for_timeout(1000)

    def type_and_include(self, input_element, text):
        input_element.fill("")  # Clear the input field
        for char in text:
            input_element.type(char)
            self.page.wait_for_timeout(50)  # Small delay between characters
        self.page.wait_for_timeout(1000)  # Wait for suggestions to appear
        
        # Press down arrow to select the first suggestion
        input_element.press('ArrowDown')
        self.page.wait_for_timeout(500)  # Wait after pressing down arrow
        
        # Press Enter to confirm the selection
        input_element.press('Enter')
        self.page.wait_for_timeout(1000)  # Wait after pressing Enter

    def type_and_exclude(self, input_element, text):
        input_element.fill("")  # Clear the input field
        for char in text:
            input_element.type(char)
            self.page.wait_for_timeout(50)  # Small delay between characters
        self.page.wait_for_timeout(1000)  # Wait for suggestions to appear
        
        # Click the first "Exclude" button
        exclude_button = self.page.locator('div[aria-label*="Exclude"]').first
        if exclude_button.count() > 0:
            exclude_button.click()
        else:
            raise Exception(f"Exclude button not found for {text}")
        
        self.page.wait_for_timeout(1000)  # Wait after clicking Exclude


    def search_whole_pages(self):
        if "Request Timed Out" in self.page.content():
            self.page.reload()

        self.page.wait_for_timeout(4000)

        number_of_searches_element = self.page.locator(".p4 .t-14.align-items-center span")
        number_of_searches = number_of_searches_element.inner_text().split(" ")[0]

        print(f"\n-> Found {number_of_searches} prospects in total")

        prospects = []
        page_num = 1
        while len(prospects) < 50:
            print(f"\n-> Processing page {page_num}")
            try:
                # Wait for the list container to be visible
                self.page.wait_for_selector('.artdeco-list', state="visible", timeout=10000)
                
                # Force load all entries
                self.force_load_entries()
                
                # Get all visible entries
                all_entries = self.page.query_selector_all(".artdeco-list__item")
                print(f"-> Found {len(all_entries)} entries on this page")

                for entry in all_entries:
                    if len(prospects) >= 50:
                        break

                    name = entry.query_selector('[data-anonymize="person-name"]')
                    title = entry.query_selector('[data-anonymize="title"]')
                    company = entry.query_selector('[data-view-name="search-results-lead-company-name"]')
                    location = entry.query_selector('[data-anonymize="location"]')
                    profile_link = entry.query_selector('a[data-view-name="search-results-lead-name"]')

                    if all([name, title, company, location, profile_link]):
                        prospects.append({
                            "name": name.inner_text(),
                            "title": title.inner_text(),
                            "company": company.inner_text(),
                            "location": location.inner_text(),
                            "profile_link": profile_link.get_attribute('href'),
                        })
                        print(f"-> Added prospect: {name.inner_text()}")

                print(f"-> Found {len(prospects)} prospects so far")

                if len(prospects) >= 50:
                    break

                next_button = self.page.locator('button[aria-label="Next"]')
                if "disabled" in next_button.get_attribute("class"):
                    print("-> Reached last page")
                    break

                next_button.click()
                print("-> Clicked next page")
                self.page.wait_for_timeout(5000)  # Increased wait time after clicking next

                page_num += 1

            except Exception as e:
                print(f"-> Error occurred: {e}")
                print("-> Moving to next page...")

        print(f"\n-> Finished collecting prospects. Total found: {len(prospects)}")
        return prospects[:50]  # Ensure we return at most 50 prospects

    def force_load_entries(self):
        print("-> Forcing load of all entries")
        last_entry_count = 0
        while True:
            # Scroll to bottom
            self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            self.page.wait_for_timeout(1000)

            # Try to force load by hovering over each entry
            entries = self.page.query_selector_all(".artdeco-list__item")
            for entry in entries:
                try:
                    entry.hover()
                    self.page.wait_for_timeout(100)  # Short wait after each hover
                except:
                    pass  # If we can't hover over an element, just continue

            # Check if we've loaded more entries
            current_entry_count = len(self.page.query_selector_all(".artdeco-list__item"))
            print(f"-> Current entry count: {current_entry_count}")
            
            if current_entry_count == last_entry_count:
                print("-> No more entries loaded")
                break
            
            last_entry_count = current_entry_count

        # Scroll back to top
        self.page.evaluate('window.scrollTo(0, 0)')
        self.page.wait_for_timeout(1000)
        print("-> Scrolled back to top")


        
    def add_contacts(self):
        full_start = time.time()

        print("\n\n-> Starting LinkedIn Sales Automation\n")

        if not self.login():
            return

        self.set_filters()
        prospects = self.search_whole_pages()

        save_data_into_json("prospects", [prospects])
        print("\n-> Data saved into prospects.json")

        print("\n-> Ending LinkedIn Sales Automation\n")

        return prospects