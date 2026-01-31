from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from functools import wraps
from models import db, User, Product, Category, CartItem, Order, OrderItem, SiteSettings
from config import Config
import os
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

# Criar pasta de uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Decorator para admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acesso negado. Área restrita para administradores.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Context processor para carrinho
@app.context_processor
def cart_count():
    if current_user.is_authenticated:
        count = CartItem.query.filter_by(user_id=current_user.id).count()
    else:
        count = len(session.get('cart', []))
    return dict(cart_count=count)

# ==================== ROTAS PÚBLICAS ====================

@app.route('/')
def index():
    featured_products = Product.query.filter_by(is_available=True, is_featured=True).limit(6).all()
    all_products = Product.query.filter_by(is_available=True).order_by(Product.created_at.desc()).all()
    categories = Category.query.all()
    settings = SiteSettings.query.first()
    return render_template('index.html', 
                         featured_products=featured_products,
                         products=all_products,
                         categories=categories,
                         settings=settings)

@app.route('/produto/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    product.views += 1
    db.session.commit()
    related = Product.query.filter(Product.id != id, Product.is_available == True).limit(4).all()
    return render_template('product_detail.html', product=product, related=related)

@app.route('/categoria/<int:id>')
def category(id):
    cat = Category.query.get_or_404(id)
    products = Product.query.filter_by(category_id=id, is_available=True).all()
    categories = Category.query.all()
    return render_template('index.html', products=products, categories=categories, current_category=cat)

@app.route('/buscar')
def search():
    query = request.args.get('q', '')
    products = Product.query.filter(
        Product.name.contains(query) | Product.description.contains(query),
        Product.is_available == True
    ).all()
    categories = Category.query.all()
    return render_template('index.html', products=products, categories=categories, search_query=query)

# ==================== AUTENTICAÇÃO ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(next_page or url_for('index'))
        flash('Email ou senha inválidos.', 'danger')
    
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            flash('As senhas não coincidem.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Este email já está cadastrado.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Este nome de usuário já está em uso.', 'danger')
            return render_template('register.html')
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Conta criada com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))

# ==================== CARRINHO ====================

@app.route('/carrinho')
def cart():
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        total = sum(item.product.price * item.quantity for item in cart_items)
    else:
        cart_items = []
        cart_ids = session.get('cart', [])
        for pid in cart_ids:
            product = Product.query.get(pid)
            if product:
                cart_items.append({'product': product, 'quantity': 1})
        total = sum(item['product'].price for item in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/carrinho/adicionar/<int:product_id>')
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    
    if not product.is_available:
        flash('Este produto não está mais disponível.', 'warning')
        return redirect(url_for('index'))
    
    if current_user.is_authenticated:
        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            flash('Este item já está no seu carrinho.', 'info')
        else:
            cart_item = CartItem(user_id=current_user.id, product_id=product_id)
            db.session.add(cart_item)
            db.session.commit()
            flash('Produto adicionado ao carrinho!', 'success')
    else:
        cart = session.get('cart', [])
        if product_id not in cart:
            cart.append(product_id)
            session['cart'] = cart
            flash('Produto adicionado ao carrinho!', 'success')
        else:
            flash('Este item já está no seu carrinho.', 'info')
    
    return redirect(url_for('cart'))

@app.route('/carrinho/remover/<int:product_id>')
def remove_from_cart(product_id):
    if current_user.is_authenticated:
        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()
    else:
        cart = session.get('cart', [])
        if product_id in cart:
            cart.remove(product_id)
            session['cart'] = cart
    
    flash('Produto removido do carrinho.', 'info')
    return redirect(url_for('cart'))

# ==================== CHECKOUT ====================

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        total = sum(item.product.price * item.quantity for item in cart_items)
    else:
        cart_items = []
        cart_ids = session.get('cart', [])
        for pid in cart_ids:
            product = Product.query.get(pid)
            if product:
                cart_items.append({'product': product, 'quantity': 1})
        total = sum(item['product'].price for item in cart_items)
    
    if not cart_items:
        flash('Seu carrinho está vazio.', 'warning')
        return redirect(url_for('index'))
    
    settings = SiteSettings.query.first()
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        payment = request.form.get('payment_method')
        notes = request.form.get('notes')
        
        # Criar pedido
        order = Order(
            user_id=current_user.id if current_user.is_authenticated else 0,
            total=total,
            payment_method=payment,
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            notes=notes
        )
        db.session.add(order)
        db.session.flush()
        
        # Adicionar itens
        if current_user.is_authenticated:
            for item in cart_items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item.product.id,
                    product_name=item.product.name,
                    price=item.product.price,
                    quantity=item.quantity
                )
                db.session.add(order_item)
                # Marcar produto como indisponível (conta vendida)
                item.product.is_available = False
                db.session.delete(item)
        else:
            for item in cart_items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item['product'].id,
                    product_name=item['product'].name,
                    price=item['product'].price,
                    quantity=item['quantity']
                )
                db.session.add(order_item)
                item['product'].is_available = False
            session['cart'] = []
        
        db.session.commit()
        flash('Pedido realizado com sucesso! Aguarde a confirmação do pagamento.', 'success')
        return redirect(url_for('order_success', order_id=order.id))
    
    return render_template('checkout.html', cart_items=cart_items, total=total, settings=settings)

@app.route('/pedido/sucesso/<int:order_id>')
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    settings = SiteSettings.query.first()
    return render_template('order_success.html', order=order, settings=settings)

@app.route('/meus-pedidos')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)

# ==================== PAINEL ADMIN ====================

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_products = Product.query.count()
    available_products = Product.query.filter_by(is_available=True).count()
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pendente').count()
    total_users = User.query.count()
    
    # Vendas do mês
    from datetime import datetime, timedelta
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    monthly_sales = db.session.query(db.func.sum(Order.total)).filter(
        Order.created_at >= start_of_month,
        Order.status == 'pago'
    ).scalar() or 0
    
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_products=total_products,
                         available_products=available_products,
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         total_users=total_users,
                         monthly_sales=monthly_sales,
                         recent_orders=recent_orders)

# Produtos Admin
@app.route('/admin/produtos')
@login_required
@admin_required
def admin_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=products)

@app.route('/admin/produtos/adicionar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_product():
    categories = Category.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        original_price = request.form.get('original_price')
        level = request.form.get('level')
        diamonds = request.form.get('diamonds')
        skins_count = request.form.get('skins_count')
        characters = request.form.get('characters')
        rank = request.form.get('rank')
        category_id = request.form.get('category_id')
        is_featured = 'is_featured' in request.form
        
        # Upload de imagem
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        product = Product(
            name=name,
            description=description,
            price=price,
            original_price=float(original_price) if original_price else None,
            image=image_filename,
            level=int(level) if level else None,
            diamonds=int(diamonds) if diamonds else 0,
            skins_count=int(skins_count) if skins_count else 0,
            characters=characters,
            rank=rank,
            category_id=int(category_id) if category_id else None,
            is_featured=is_featured
        )
        db.session.add(product)
        db.session.commit()
        
        flash('Produto adicionado com sucesso!', 'success')
        return redirect(url_for('admin_products'))
    
    return render_template('admin/add_product.html', categories=categories)

@app.route('/admin/produtos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_product(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.all()
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.original_price = float(request.form.get('original_price')) if request.form.get('original_price') else None
        product.level = int(request.form.get('level')) if request.form.get('level') else None
        product.diamonds = int(request.form.get('diamonds')) if request.form.get('diamonds') else 0
        product.skins_count = int(request.form.get('skins_count')) if request.form.get('skins_count') else 0
        product.characters = request.form.get('characters')
        product.rank = request.form.get('rank')
        product.category_id = int(request.form.get('category_id')) if request.form.get('category_id') else None
        product.is_featured = 'is_featured' in request.form
        product.is_available = 'is_available' in request.form
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                product.image = filename
        
        db.session.commit()
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('admin_products'))
    
    return render_template('admin/edit_product.html', product=product, categories=categories)

@app.route('/admin/produtos/excluir/<int:id>')
@login_required
@admin_required
def admin_delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Produto excluído com sucesso!', 'success')
    return redirect(url_for('admin_products'))

# Categorias Admin
@app.route('/admin/categorias', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_categories():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            category = Category(name=name)
            db.session.add(category)
            db.session.commit()
            flash('Categoria adicionada!', 'success')
    
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categorias/excluir/<int:id>')
@login_required
@admin_required
def admin_delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    flash('Categoria excluída!', 'success')
    return redirect(url_for('admin_categories'))

# Pedidos Admin
@app.route('/admin/pedidos')
@login_required
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/pedidos/<int:id>')
@login_required
@admin_required
def admin_order_detail(id):
    order = Order.query.get_or_404(id)
    return render_template('admin/order_detail.html', order=order)

@app.route('/admin/pedidos/<int:id>/status', methods=['POST'])
@login_required
@admin_required
def admin_update_order_status(id):
    order = Order.query.get_or_404(id)
    new_status = request.form.get('status')
    order.status = new_status
    db.session.commit()
    flash(f'Status do pedido atualizado para: {new_status}', 'success')
    return redirect(url_for('admin_order_detail', id=id))

# Usuários Admin
@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/usuarios/<int:id>/toggle-admin')
@login_required
@admin_required
def admin_toggle_admin(id):
    user = User.query.get_or_404(id)
    if user.id != current_user.id:
        user.is_admin = not user.is_admin
        db.session.commit()
        flash(f'Permissões de {user.username} atualizadas!', 'success')
    return redirect(url_for('admin_users'))

# Configurações Admin
@app.route('/admin/configuracoes', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    settings = SiteSettings.query.first()
    if not settings:
        settings = SiteSettings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        settings.site_name = request.form.get('site_name')
        settings.whatsapp = request.form.get('whatsapp')
        settings.instagram = request.form.get('instagram')
        settings.pix_key = request.form.get('pix_key')
        settings.banner_text = request.form.get('banner_text')
        db.session.commit()
        flash('Configurações salvas!', 'success')
    
    return render_template('admin/settings.html', settings=settings)

# ==================== INICIALIZAÇÃO ====================

def create_tables():
    with app.app_context():
        db.create_all()
        
        # Criar admin padrão se não existir
        admin = User.query.filter_by(email='admin@admin.com').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@admin.com',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
        
        # Criar configurações padrão
        settings = SiteSettings.query.first()
        if not settings:
            settings = SiteSettings(
                site_name='🔥 FF Store - Contas Free Fire',
                whatsapp='5511999999999',
                banner_text='🎮 As melhores contas de Free Fire você encontra aqui!'
            )
            db.session.add(settings)
        
        # Criar categorias padrão
        if not Category.query.first():
            categories = ['Contas Bronze', 'Contas Prata', 'Contas Ouro', 'Contas Diamante', 'Contas Mestre', 'Contas Grandmaster']
            for cat_name in categories:
                db.session.add(Category(name=cat_name))
        
        db.session.commit()

if __name__ == '__main__':
    create_tables()
    app.run(debug=True)