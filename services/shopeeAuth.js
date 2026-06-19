export async function loginShopee(browser) {
  const context = await browser.newContext();
  const page = await context.newPage();
  
  try {
    console.log('Navigating to Shopee Affiliate login page...');
    await page.goto('https://affiliate.shopee.co.id/');
    
    console.log('Please log in to Shopee Affiliate manually. Waiting for dashboard...');
    
    // Wait for URL matching the dashboard pattern
    await page.waitForURL(/affiliate\.shopee\.co\.id\/dashboard/, {
      timeout: 5 * 60 * 1000 // 5 minutes
    });
    
    console.log('Login successful! Saving session state...');
    
    // Save storage state to shopee_state.json
    await context.storageState({ path: 'shopee_state.json' });
    
    console.log('Shopee session saved to shopee_state.json');
    
  } catch (error) {
    if (error.name === 'TimeoutError') {
      console.error('Timeout: User did not complete login within 5 minutes');
    } else {
      console.error('Error during Shopee login:', error.message);
    }
    throw error;
  } finally {
    await context.close();
  }
}