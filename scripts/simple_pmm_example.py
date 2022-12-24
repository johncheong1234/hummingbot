import logging
from decimal import Decimal
from typing import List

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate, PerpetualOrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimplePMM(ScriptStrategyBase):
    bid_spread = 0.08
    ask_spread = 0.08
    order_refresh_time = 15
    order_amount = 100
    create_timestamp = 0
    trading_pair = "LTC-USDT"
    exchange = "binance_perpetual_testnet"
    # Here you can use for example the LastTrade price to use in your strategy
    price_source = PriceType.MidPrice

    markets = {exchange: {trading_pair}}

    def on_tick(self):
        orderBook = self.connectors[self.exchange].get_order_book(self.trading_pair)
        # print snapshot of orderBook
        self.logger().info(f"OrderBook: {orderBook}")
        # ask_entries
        # ask_entries = orderBook.ask_entries()
        # print ask_entries
        # for ask_entry in ask_entries:
        #     self.logger().info(f"Ask Entry: {ask_entry}")

        buyPrice = self.connectors[self.exchange].get_price(self.trading_pair, is_buy = True)
        sellPrice = self.connectors[self.exchange].get_price(self.trading_pair, is_buy = False)
        midPrice = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        self.logger().info(f"buyPrice: {buyPrice}")
        self.logger().info(f"sellPrice: {sellPrice}")
        self.logger().info(f"midPrice: {midPrice}")

        accountPosition = self.connectors[self.exchange].account_positions
        # self.logger().info(f"Account Position: {accountPosition}")

        # iterate through dictionary accountPosition and print key and value
        amount = 0
        unrealized_pnl = 0
        for key, value in accountPosition.items():
            trading_pair = value.trading_pair
            if (trading_pair == self.trading_pair):
                amount = value.amount
                unrealized_pnl = value.unrealized_pnl
                self.logger().info(f"Key: {key}, Value: {value}, type: {type(value)}")

        self.logger().info(f"Amount: {amount}, type: {type(amount)}")
        self.logger().info(f"Unrealized PnL: {unrealized_pnl}, type: {type(unrealized_pnl)}")

        if self.create_timestamp <= self.current_timestamp and amount == 0:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

    def create_proposal(self) -> List[OrderCandidate]:
        # ref_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        # buy_price = ref_price * Decimal(1 - self.bid_spread)
        # sell_price = ref_price * Decimal(1 + self.ask_spread)

        buy_order = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal(self.order_amount),
            price=Decimal(70),
            from_total_balances=True,
            leverage=Decimal(1),
            position_close=False,
        )

        return [buy_order]

        # sell_order = PerpetualOrderCandidate(
        #     trading_pair=self.trading_pair,
        #     is_maker=True,
        #     order_type=OrderType.LIMIT,
        #     order_side=TradeType.SELL,
        #     amount=Decimal(self.order_amount),
        #     price=sell_price,
        #     from_total_balances=True,
        #     leverage=Decimal(1),
        #     position_close=False,
        # )

        # return [buy_order, sell_order]

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )
        elif order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.exchange} at {round(event.price, 2)}"
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
