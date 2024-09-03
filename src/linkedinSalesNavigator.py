# src/linkedinSalesNavigator.py

import time
import re
from playwright.async_api import Page
from collections import defaultdict
from src.utils.utils import save_data_into_json
from tenacity import retry, stop_after_attempt, wait_fixed

def sanitize_text(text):
    return re.sub(r'[^a-zA-Z0-9\s]', '', text)

class LinkedInSalesNavigator:
    def __init__(self, CONFIGS, page: Page):
        self.CONFIGS = CONFIGS
        self.page = page
        self.base_url = CONFIGS["BaseUrl"]
        self.analyzed_job_posts = []

    async def login(self):
        print("-> Logging into LinkedIn")
        await self.page.goto(self.base_url)
        await self.page.wait_for_timeout(3000)

        content = await self.page.content()
        if "Login screen" in content:
            print("-> Login required. Please check your cookies.")
            return False

        print("-> Successfully logged into LinkedIn")
        return True

    async def set_filters(self):
        print("\n-> Setting Filters")
        try:
            await self.set_company_filters()
            await self.set_job_title_filters()
            await self.set_seniority_level_filters()
            
            if self.CONFIGS["OnlyUSProspects"]:
                await self.set_location_filters()

            await self.page.click('[aria-label="Collapse filter panel"]')
        except Exception as e:
            print(f"Fatal error in setting filters: {str(e)}")
            print("Aborting the automation process due to filter setting failure.")
            raise

    async def set_company_filters(self):
        print("-> Setting Company Filters")
        for job_post in self.analyzed_job_posts:
            try:
                await self.page.wait_for_selector('fieldset [title="Current company"] li-icon[type="plus-icon"]', state="visible")
                await self.page.click('fieldset [title="Current company"] li-icon[type="plus-icon"]')
                company_input = self.page.locator('fieldset [title="Current company"] input')
                await company_input.wait_for(state="visible")
                
                sanitized_company = sanitize_text(job_post["company_name"])
                await company_input.fill(sanitized_company)

                await self.page.wait_for_timeout(200)

                options = self.page.locator('ul[role="listbox"] li')
                found = False
                async for option in options.all():
                    if sanitized_company.lower() in sanitize_text(await option.inner_text()).lower():
                        await option.click()
                        found = True
                        break

                if not found:
                    print(f"-> Failed to find Company: {sanitized_company}")
                    if self.CONFIGS["UseFirstOption"]:
                        await options.first.click()
                    elif self.CONFIGS["UseSearchQuery"]:
                        await company_input.press('Enter')

                # Verify the filter was applied
                applied_filters = self.page.locator('fieldset [title="Current company"] .artdeco-pill')
                if await applied_filters.count() == 0:
                    print(f"Warning: Filter for '{sanitized_company}' may not have been applied.")

            except Exception as e:
                print(f"Error setting company filter for '{sanitized_company}': {str(e)}")
                continue

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def set_single_job_title_filter(self, job_title, is_first_entry=False):
        print(f"  -> Setting filter for job title: {job_title}")
        
        # Look for the input field
        title_input = self.page.locator('input[placeholder="Add current titles"]')
        if await title_input.count() == 0:
            # If not found, we might need to open the job title filter section
            await self.page.click('fieldset [title="Current job title"] li-icon[type="plus-icon"]')
            title_input = self.page.locator('input[placeholder="Add current titles"]')
        
        await title_input.wait_for(state="visible")
        
        # Clear the input field
        await title_input.fill("")
        
        sanitized_title = sanitize_text(job_title)
        
        # Type out the job title character by character
        for char in sanitized_title:
            await title_input.type(char)
            await self.page.wait_for_timeout(50)  # Small delay between characters
        
        print(f"  -> Typed job title: {sanitized_title}")
        await self.page.wait_for_timeout(100)
        
        if is_first_entry:
            # For the first entry, wait for suggestions and click the first one
            try:
                await self.page.wait_for_selector('ul[role="listbox"]', state="visible", timeout=5000)
                await self.page.click('ul[role="listbox"] li:first-child')
                print("  -> Clicked first suggestion")
            except Exception as e:
                print(f"  -> No suggestions appeared for first entry. Pressing Enter. Error: {str(e)}")
                await title_input.press('Enter')
        else:
            # For subsequent entries, just press Enter
            print("  -> Subsequent entry: Pressing Enter")
            await title_input.press('Enter')
        
        # Verify the filter was applied
        await self.page.wait_for_timeout(1000)
        applied_filters = self.page.locator('fieldset [title="Current job title"] .artdeco-pill')
        if await applied_filters.count() == 0:
            raise Exception(f"Filter for '{sanitized_title}' was not applied.")
        
        print(f"  -> Filter applied successfully for: {sanitized_title}")
        
        # Wait for any animations or UI updates to complete
        await self.page.wait_for_timeout(1000)

    async def set_job_title_filters(self):
        print("-> Setting Job Title Filters")
        for index, job_title in enumerate(self.CONFIGS["RequiredJobTitles"]):
            try:
                print(f"  -> Attempting to set filter for job title {index + 1}: {job_title}")
                await self.set_single_job_title_filter(job_title, is_first_entry=(index == 0))
                print(f"  -> Successfully set filter for job title {index + 1}: {job_title}")
            except Exception as e:
                print(f"Error setting job title filter for '{job_title}': {str(e)}")
            
            # Check if the filter was actually applied
            applied_filters = self.page.locator('fieldset [title="Current job title"] .artdeco-pill')
            applied_count = await applied_filters.count()
            print(f"  -> Current number of applied job title filters: {applied_count}")
            
            # Wait for any UI updates
            await self.page.wait_for_timeout(1000)
        
        print("-> Finished attempting to set all job title filters")
        # After setting all filters, wait for any final UI updates
        await self.page.wait_for_timeout(1000)
        
        # Final verification of all applied filters
        applied_filters = self.page.locator('fieldset [title="Current job title"] .artdeco-pill')
        applied_count = await applied_filters.count()
        expected_count = len(self.CONFIGS["RequiredJobTitles"])
        if applied_count != expected_count:
            print(f"Warning: Expected {expected_count} job title filters, but found {applied_count}")
        else:
            print(f"Successfully applied all {applied_count} job title filters")

    async def set_seniority_level_filters(self):
        print("-> Setting Seniority Level Filters")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Click to expand the Seniority level filter if it's collapsed
                expand_button = self.page.locator('fieldset[title="Seniority level"] button[aria-expanded="false"]')
                if await expand_button.count() > 0:
                    await expand_button.click()
                    await self.page.wait_for_timeout(1000)

                for index, seniority_level in enumerate(self.CONFIGS["RequiredSeniorityLevels"]):
                    print(f"  -> Setting filter for seniority level: {seniority_level}")
                    
                    # Look for the specific seniority level option
                    option_selector = f'li[aria-label*="{seniority_level}" i]'
                    option = self.page.locator(option_selector)
                    
                    if await option.count() > 0:
                        # Click the "Include" button for this seniority level
                        include_button = option.locator('div[aria-label*="Include" i]')
                        if await include_button.count() > 0:
                            await include_button.click()
                            print(f"  -> Included: {seniority_level}")
                            
                            # Add a longer delay after selecting the first seniority level
                            if index == 0:
                                await self.page.wait_for_timeout(2000)  # 2 second delay after the first selection
                            else:
                                await self.page.wait_for_timeout(1000)  # 1 second delay for subsequent selections
                        else:
                            print(f"  -> Warning: Include button not found for '{seniority_level}'")
                    else:
                        print(f"  -> Warning: Seniority level '{seniority_level}' not found")

                # Verify the filters were applied
                applied_filters = self.page.locator('fieldset[title="Seniority level"] .artdeco-pill')
                applied_count = await applied_filters.count()
                print(f"  -> Applied {applied_count} seniority level filters")

                if applied_count != len(self.CONFIGS["RequiredSeniorityLevels"]):
                    raise Exception(f"Not all seniority level filters were applied. Expected: {len(self.CONFIGS['RequiredSeniorityLevels'])}, Applied: {applied_count}")

                print("  -> All seniority level filters applied successfully")
                return  # Exit the method if successful

            except Exception as e:
                print(f"Error setting seniority level filters (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print("  -> Retrying...")
                    await self.page.wait_for_timeout(2000)  # Wait before retrying
                else:
                    print("  -> Max retries reached. Aborting seniority level filter setting.")
                    raise  # Re-raise the exception to stop the entire process

        # Wait for any UI updates
        await self.page.wait_for_timeout(1000)

    async def set_location_filters(self):
        print("-> Setting Location Filters")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Expand the Geography filter if it's collapsed
                expand_button = self.page.locator('fieldset[title="Geography"] button[aria-expanded="false"]')
                if await expand_button.count() > 0:
                    await expand_button.click()
                    await self.page.wait_for_timeout(1000)

                # Look for the input field
                geography_input = self.page.locator('input[placeholder="Add locations"]')
                if await geography_input.count() == 0:
                    # If not found, we might need to open the geography filter section
                    await self.page.click('fieldset[title="Geography"] li-icon[type="plus-icon"]')
                    geography_input = self.page.locator('input[placeholder="Add locations"]')
                
                await geography_input.wait_for(state="visible")

                # Include United States
                await self.type_and_include(geography_input, "United States")
                print("  -> Included: United States")

                # Exclude specified states
                for state in self.CONFIGS["StatesToExclude"]:
                    await self.type_and_exclude(geography_input, state)
                    print(f"  -> Excluded: {state}")

                await self.page.wait_for_timeout(2000)  # Wait for the UI to update

                # Verify the filters were applied
                applied_filters = self.page.locator('fieldset[title="Geography"] .artdeco-pill')
                applied_count = await applied_filters.count()
                expected_count = 1 + len(self.CONFIGS["StatesToExclude"])  # United States + excluded states
                
                if applied_count != expected_count:
                    raise Exception(f"Not all location filters were applied. Expected: {expected_count}, Applied: {applied_count}")

                print(f"  -> Successfully applied {applied_count} location filters")
                return  # Exit the method if successful

            except Exception as e:
                print(f"Error setting location filters (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print("  -> Retrying...")
                    await self.page.wait_for_timeout(2000)  # Wait before retrying
                else:
                    print("  -> Max retries reached. Aborting location filter setting.")
                    raise  # Re-raise the exception to stop the entire process

        # Wait for any UI updates
        await self.page.wait_for_timeout(1000)

    async def type_and_include(self, input_element, text):
        await input_element.fill("")  # Clear the input field
        for char in text:
            await input_element.type(char)
            await self.page.wait_for_timeout(50)  # Small delay between characters
        await self.page.wait_for_timeout(1000)  # Wait for suggestions to appear
        
        # Press down arrow to select the first suggestion
        await input_element.press('ArrowDown')
        await self.page.wait_for_timeout(500)  # Wait after pressing down arrow
        
        # Press Enter to confirm the selection
        await input_element.press('Enter')
        await self.page.wait_for_timeout(1000)  # Wait after pressing Enter

    async def type_and_exclude(self, input_element, text):
        await input_element.fill("")  # Clear the input field
        for char in text:
            await input_element.type(char)
            await self.page.wait_for_timeout(50)  # Small delay between characters
        await self.page.wait_for_timeout(1000)  # Wait for suggestions to appear
        
        # Click the first "Exclude" button
        exclude_button = self.page.locator('div[aria-label*="Exclude"]').first
        if await exclude_button.count() > 0:
            await exclude_button.click()
        else:
            raise Exception(f"Exclude button not found for {text}")
        
        await self.page.wait_for_timeout(1000)  # Wait after clicking Exclude

    async def search_whole_pages(self):
        if "Request Timed Out" in await self.page.content():
            await self.page.reload()

        await self.page.wait_for_timeout(4000)

        try:
            number_of_searches_element = self.page.locator(".p4 .t-14.align-items-center span").filter(has_text="results")
            number_of_searches_text = await number_of_searches_element.inner_text()
            number_of_searches = number_of_searches_text.split()[0].replace(',', '')
            print(f"\n-> Found {number_of_searches} prospects in total")
        except Exception as e:
            print(f"Error getting number of searches: {str(e)}")
            number_of_searches = "unknown"

        prospects = []
        page_num = 1
        while len(prospects) < 50:
            print(f"\n-> Processing page {page_num}")
            try:
                await self.page.wait_for_selector('.artdeco-list', state="visible", timeout=10000)
                
                await self.force_load_entries()
                
                all_entries = await self.page.query_selector_all(".artdeco-list__item")
                print(f"-> Found {len(all_entries)} entries on this page")

                for entry in all_entries:
                    if len(prospects) >= 50:
                        break

                    name = await entry.query_selector('[data-anonymize="person-name"]')
                    title = await entry.query_selector('[data-anonymize="title"]')
                    company = await entry.query_selector('[data-view-name="search-results-lead-company-name"]')
                    location = await entry.query_selector('[data-anonymize="location"]')
                    profile_link = await entry.query_selector('a[data-view-name="search-results-lead-name"]')

                    if all([name, title, company, location, profile_link]):
                        prospects.append({
                            "name": await name.inner_text(),
                            "title": await title.inner_text(),
                            "company": await company.inner_text(),
                            "location": await location.inner_text(),
                            "profile_link": await profile_link.get_attribute('href'),
                        })
                        print(f"-> Added prospect: {await name.inner_text()}")

                print(f"-> Found {len(prospects)} prospects so far")

                if len(prospects) >= 50:
                    break

                next_button = self.page.locator('button[aria-label="Next"]')
                if "disabled" in await next_button.get_attribute("class"):
                    print("-> Reached last page")
                    break

                await next_button.click()
                print("-> Clicked next page")
                await self.page.wait_for_timeout(5000)

                page_num += 1

            except Exception as e:
                print(f"-> Error occurred: {e}")
                print("-> Moving to next page...")

        print(f"\n-> Finished collecting prospects. Total found: {len(prospects)}")
        return prospects[:50]

    async def force_load_entries(self):
        print("-> Forcing load of all entries")
        last_entry_count = 0
        while True:
            # Scroll to bottom
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await self.page.wait_for_timeout(1000)

            # Try to force load by hovering over each entry
            entries = await self.page.query_selector_all(".artdeco-list__item")
            for entry in entries:
                try:
                    await entry.hover()
                    await self.page.wait_for_timeout(100)  # Short wait after each hover
                except:
                    pass  # If we can't hover over an element, just continue

            # Check if we've loaded more entries
            current_entry_count = len(await self.page.query_selector_all(".artdeco-list__item"))
            print(f"-> Current entry count: {current_entry_count}")
            
            if current_entry_count == last_entry_count:
                print("-> No more entries loaded")
                break
            
            last_entry_count = current_entry_count

        # Scroll back to top
        await self.page.evaluate('window.scrollTo(0, 0)')
        await self.page.wait_for_timeout(1000)
        print("-> Scrolled back to top")