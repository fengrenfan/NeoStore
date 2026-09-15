/**
 * Storefront copy.
 *
 * Product text comes from the API (that is the whole point of the translation
 * tables); this file only holds the shop's own chrome. Keys are kept flat and
 * complete for every locale so a missing string is a type error rather than a
 * blank space on the page.
 */

export interface Copy {
  tagline: string;
  navHome: string;
  navProducts: string;
  navCart: string;
  localeLabels: Record<string, string>;
  heroTitle: string;
  heroSubtitle: string;
  heroCta: string;
  featuredTitle: string;
  productsTitle: string;
  productsCount: (shown: number, total: number) => string;
  productsEmpty: string;
  addToCart: string;
  adding: string;
  added: string;
  viewCart: string;
  chooseVariant: string;
  /** Noun only; the count is appended by the component, e.g. "库存 12". */
  inStockLabel: string;
  outOfStock: string;
  soldOut: string;
  sku: string;
  description: string;
  cartTitle: string;
  cartEmpty: string;
  continueShopping: string;
  subtotal: string;
  shipping: string;
  free: string;
  tax: string;
  total: string;
  toCheckout: string;
  remove: string;
  quantity: string;
  checkoutTitle: string;
  email: string;
  fullName: string;
  addressLine1: string;
  addressLine2: string;
  city: string;
  postalCode: string;
  country: string;
  placeOrder: string;
  placingOrder: string;
  paymentNote: string;
  orderTitle: string;
  orderNumber: string;
  orderStatus: string;
  orderPlaced: string;
  orderThanks: (email: string) => string;
  backToShop: string;
  simulatePayment: string;
  simulating: string;
  paymentConfirmed: string;
  orderNotFound: string;
  somethingWentWrong: string;
  retry: string;
  loading: string;
  footerNote: string;
}

const ZH: Copy = {
  tagline: "跨境直邮 · 多语言多币种",
  navHome: "首页",
  navProducts: "全部商品",
  navCart: "购物车",
  localeLabels: { "zh-CN": "简体中文", en: "English", ja: "日本語" },
  heroTitle: "把好设计寄到全世界",
  heroSubtitle: "一次上架，多语言、多币种自动就绪。下单即刻锁库存，价格按下单地区实时换算。",
  heroCta: "开始选购",
  featuredTitle: "精选商品",
  productsTitle: "全部商品",
  productsCount: (shown, total) => `显示 ${shown} / ${total} 件商品`,
  productsEmpty: "该地区暂时没有上架商品。",
  addToCart: "加入购物车",
  adding: "正在加入…",
  added: "已加入购物车",
  viewCart: "查看购物车",
  chooseVariant: "请选择规格",
  inStockLabel: "库存",
  outOfStock: "暂时缺货",
  soldOut: "已售罄",
  sku: "货号",
  description: "商品详情",
  cartTitle: "购物车",
  cartEmpty: "购物车还是空的。",
  continueShopping: "继续挑选",
  subtotal: "商品小计",
  shipping: "运费",
  free: "免运费",
  tax: "税费",
  total: "应付合计",
  toCheckout: "去结算",
  remove: "移除",
  quantity: "数量",
  checkoutTitle: "填写收货信息",
  email: "邮箱",
  fullName: "收件人",
  addressLine1: "详细地址",
  addressLine2: "门牌 / 楼层（选填）",
  city: "城市",
  postalCode: "邮政编码",
  country: "国家 / 地区",
  placeOrder: "提交订单",
  placingOrder: "正在提交…",
  paymentNote: "当前接入的是模拟支付网关，提交后订单会进入「待支付」，可在订单页完成模拟支付。",
  orderTitle: "订单详情",
  orderNumber: "订单号",
  orderStatus: "订单状态",
  orderPlaced: "下单时间",
  orderThanks: (email) => `下单成功，确认邮件将发送至 ${email}。`,
  backToShop: "返回商店",
  simulatePayment: "模拟支付",
  simulating: "支付中…",
  paymentConfirmed: "支付已确认，库存已扣减。",
  orderNotFound: "没有找到这个订单。",
  somethingWentWrong: "出了点问题，请稍后再试。",
  retry: "重试",
  loading: "加载中…",
  footerNote: "NeoStore · 演示用跨境独立站",
};

const EN: Copy = {
  tagline: "Worldwide shipping · multi-language, multi-currency",
  navHome: "Home",
  navProducts: "All products",
  navCart: "Cart",
  localeLabels: { "zh-CN": "简体中文", en: "English", ja: "日本語" },
  heroTitle: "Good design, shipped anywhere",
  heroSubtitle:
    "List once and every language and currency is ready. Stock is reserved at checkout and prices convert for the buyer's region.",
  heroCta: "Start shopping",
  featuredTitle: "Featured",
  productsTitle: "All products",
  productsCount: (shown, total) => `Showing ${shown} of ${total} products`,
  productsEmpty: "Nothing is listed for this region yet.",
  addToCart: "Add to cart",
  adding: "Adding…",
  added: "Added to your cart",
  viewCart: "View cart",
  chooseVariant: "Choose an option",
  inStockLabel: "In stock",
  outOfStock: "Out of stock",
  soldOut: "Sold out",
  sku: "SKU",
  description: "Details",
  cartTitle: "Your cart",
  cartEmpty: "Your cart is empty.",
  continueShopping: "Keep shopping",
  subtotal: "Subtotal",
  shipping: "Shipping",
  free: "Free",
  tax: "Tax",
  total: "Total",
  toCheckout: "Checkout",
  remove: "Remove",
  quantity: "Quantity",
  checkoutTitle: "Where should we send it?",
  email: "Email",
  fullName: "Full name",
  addressLine1: "Address",
  addressLine2: "Apartment, floor (optional)",
  city: "City",
  postalCode: "Postal code",
  country: "Country / region",
  placeOrder: "Place order",
  placingOrder: "Placing order…",
  paymentNote:
    "This build is wired to a mock payment gateway. Submitting moves the order to “awaiting payment”, and you can complete the mock payment from the order page.",
  orderTitle: "Order",
  orderNumber: "Order number",
  orderStatus: "Status",
  orderPlaced: "Placed",
  orderThanks: (email) => `Thank you — a confirmation will go to ${email}.`,
  backToShop: "Back to the shop",
  simulatePayment: "Simulate payment",
  simulating: "Confirming…",
  paymentConfirmed: "Payment confirmed and stock committed.",
  orderNotFound: "We could not find that order.",
  somethingWentWrong: "Something went wrong. Please try again.",
  retry: "Retry",
  loading: "Loading…",
  footerNote: "NeoStore · demo cross-border storefront",
};

const JA: Copy = {
  tagline: "海外直送 · 多言語・多通貨",
  navHome: "ホーム",
  navProducts: "すべての商品",
  navCart: "カート",
  localeLabels: { "zh-CN": "简体中文", en: "English", ja: "日本語" },
  heroTitle: "よいデザインを、世界中へ",
  heroSubtitle:
    "一度登録すれば多言語・多通貨が自動で揃います。注文時に在庫を確保し、価格は地域ごとに換算します。",
  heroCta: "買い物をはじめる",
  featuredTitle: "おすすめ",
  productsTitle: "すべての商品",
  productsCount: (shown, total) => `${total} 件中 ${shown} 件を表示`,
  productsEmpty: "この地域にはまだ商品がありません。",
  addToCart: "カートに追加",
  adding: "追加中…",
  added: "カートに追加しました",
  viewCart: "カートを見る",
  chooseVariant: "オプションを選択",
  inStockLabel: "在庫",
  outOfStock: "在庫切れ",
  soldOut: "完売",
  sku: "SKU",
  description: "商品詳細",
  cartTitle: "カート",
  cartEmpty: "カートは空です。",
  continueShopping: "買い物を続ける",
  subtotal: "小計",
  shipping: "送料",
  free: "無料",
  tax: "税",
  total: "合計",
  toCheckout: "レジへ進む",
  remove: "削除",
  quantity: "数量",
  checkoutTitle: "お届け先の入力",
  email: "メールアドレス",
  fullName: "お名前",
  addressLine1: "住所",
  addressLine2: "建物名・部屋番号（任意）",
  city: "市区町村",
  postalCode: "郵便番号",
  country: "国・地域",
  placeOrder: "注文を確定する",
  placingOrder: "送信中…",
  paymentNote:
    "このビルドはモック決済に接続しています。送信後は「支払い待ち」になり、注文ページでモック決済を完了できます。",
  orderTitle: "注文詳細",
  orderNumber: "注文番号",
  orderStatus: "ステータス",
  orderPlaced: "注文日時",
  orderThanks: (email) => `ご注文ありがとうございます。確認メールを ${email} 宛にお送りします。`,
  backToShop: "ストアに戻る",
  simulatePayment: "モック決済を実行",
  simulating: "確認中…",
  paymentConfirmed: "支払いを確認し、在庫を確定しました。",
  orderNotFound: "注文が見つかりません。",
  somethingWentWrong: "問題が発生しました。しばらくしてからお試しください。",
  retry: "再試行",
  loading: "読み込み中…",
  footerNote: "NeoStore · デモ用クロスボーダーストア",
};

const BY_LOCALE: Record<string, Copy> = { "zh-CN": ZH, en: EN, ja: JA };

export function copy(locale: string): Copy {
  return BY_LOCALE[locale] ?? ZH;
}
