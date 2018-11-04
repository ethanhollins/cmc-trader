from selenium import webdriver

def retrieveTicketElements(driver, pair):
	pair = pair[:3] + '-' + pair[3:]
	return driver.execute_script(
			'var ticket_elements = {};'
			'var results = [];'
			'query = document.evaluate("//div[@class=\'feature feature-next-gen-order-ticket\']", document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);'
			'for (let i = 0, length=query.snapshotLength; i<length; ++i) {'
			'	results.push(query.snapshotItem(i));'
			'}'
			'for (let i = 0; i < results.length; i++)'
			'{'
			'	console.log("> Checking ticket " + i + "...");'
			'	var elem = results[i];'
			'	try'
			'	{'
			'		var pair = arguments[0];'
			'		if ((elem_title = elem.querySelector(\'[title="\'+ pair +\'"]\')) != null)'
			'		{'
			'           console.log(elem);'
			'			ticket_elements[\'TICKET\'] = elem;'
			'			ticket_elements[\'TICKET_ID\'] = elem.getAttribute("id");'
			'			console.log("FOUND");'
			'		}'
			'	}'
			'	catch(err)'
			'	{'
			'		console.log(err.message);'
			'	}'
			'}'
			'elem_current_time = document.querySelector(\'[class="current-time"]\');'
			'ticket_elements[\'CURRENT_TIME\'] = elem_current_time;'
			'elem_seconds = elem_current_time.querySelector(\'[class="s"]\');'
			'ticket_elements[\'SECONDS\'] = elem_current_time;'
			'elem_order_type = ticket_elements[\'TICKET\'].querySelector(\'[class="order-type"]\');'
			'ticket_elements[\'ORDER_TYPE\'] = elem_order_type;'
			'elem_market = elem_order_type.querySelector(\'[data-value="MARKET"]\');'
			'ticket_elements[\'MARKET\'] = elem_market;'
			'elem_limit = elem_order_type.querySelector(\'[data-value="LIMIT"]\');'
			'ticket_elements[\'LIMIT\'] = elem_limit;'
			'elem_stop_entry = elem_order_type.querySelector(\'[data-value="STOP_ENTRY"]\');'
			'ticket_elements[\'STOP_ENTRY\'] = elem_stop_entry;'
			'elem_t_buy = ticket_elements[\'TICKET\'].querySelector(\'[class*="price-box buy"]\');'
			'ticket_elements[\'T_BUY\'] = elem_t_buy;'
			'elem_t_sell = ticket_elements[\'TICKET\'].querySelector(\'[class*="price-box sell"]\');'
			'ticket_elements[\'T_SELL\'] = elem_t_sell;'
			'elem_price_buy = elem_t_buy.querySelector(\'[class="price"]\').getElementsByTagName("span")[0];'
			'ticket_elements[\'PRICE_BUY\'] = elem_price_buy;'
			'elem_price_buy_dec = elem_t_buy.querySelector(\'[class="price"]\').getElementsByTagName("sub")[0];'
			'ticket_elements[\'PRICE_BUY_DEC\'] = elem_price_buy_dec;'
			'elem_price_sell = elem_t_sell.querySelector(\'[class="price"]\').getElementsByTagName("span")[0];'
			'ticket_elements[\'PRICE_SELL\'] = elem_price_sell;'
			'elem_price_sell_dec = elem_t_sell.querySelector(\'[class="price"]\').getElementsByTagName("sub")[0];'
			'ticket_elements[\'PRICE_SELL_DEC\'] = elem_price_sell_dec;'
			'elem_spread = ticket_elements[\'TICKET\'].querySelector(\'[class="spread"]\');'
			'ticket_elements[\'SPREAD\'] = elem_spread;'
			'elem_lotsize = ticket_elements[\'TICKET\'].querySelector(\'[name="quantity"]\');'
			'ticket_elements[\'LOTSIZE\'] = elem_lotsize;'
			'elem_stop_loss = ticket_elements[\'TICKET\'].querySelector(\'[class="stopLoss"]\').querySelector(\'[class*="add-child-order"]\');'
			'ticket_elements[\'STOP_LOSS\'] = elem_stop_loss;'
			'elem_stop_loss_close = ticket_elements[\'TICKET\'].querySelector(\'[class="stopLoss"]\').querySelector(\'[class="close"]\');'
			'ticket_elements[\'STOP_LOSS_CLOSE\'] = elem_stop_loss_close;'
			'elem_take_profit = ticket_elements[\'TICKET\'].querySelector(\'[class="takeProfit"]\').querySelector(\'[class*="add-child-order"]\');'
			'ticket_elements[\'TAKE_PROFIT\'] = elem_take_profit;'
			'elem_take_profit_close = ticket_elements[\'TICKET\'].querySelector(\'[class="takeProfit"]\').querySelector(\'[data-svg-icon-name="icon-close"]\');'
			'ticket_elements[\'TAKE_PROFIT_CLOSE\'] = elem_take_profit_close;'
			'elem_menu_btn = ticket_elements[\'TICKET\'].querySelector(\'[class="context-menu-button context-menu-link visible"]\');'
			'ticket_elements[\'MENU_BTN\'] = elem_menu_btn;'
			'elem_context_menu = document.querySelector(\'[class="context-menu"]\');'
			'ticket_elements[\'CONTEXT_MENU\'] = elem_context_menu;'
			'elem_submit_btn = ticket_elements[\'TICKET\'].querySelector(\'[class*="submit-button"]\');'
			'ticket_elements[\'ACTION_BTN\'] = elem_submit_btn;'
			'return ticket_elements;',
			pair
		)
	