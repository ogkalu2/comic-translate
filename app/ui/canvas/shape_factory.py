"""
Factory per la creazione di elementi di forma nel canvas.
"""

from PySide6 import QtCore, QtGui
from .shape_rect import RectangleItem
from .shape_ellipse import EllipseItem 
from .shape_balloon import BalloonItem


class ShapeFactory:
    """
    Factory per la creazione di vari tipi di forme.
    Centralizza la logica di creazione degli elementi di forma.
    """
    
    @staticmethod
    def create_shape(shape_type, x, y, width=100, height=60, **kwargs):
        """
        Crea un'istanza di forma in base al tipo specificato.
        
        Args:
            shape_type (str): Tipo di forma da creare ('rettangolo', 'ellisse', 'fumetto', ecc.)
            x (float): Posizione X iniziale
            y (float): Posizione Y iniziale
            width (float): Larghezza iniziale
            height (float): Altezza iniziale
            **kwargs: Parametri aggiuntivi specifici per il tipo di forma
            
        Returns:
            ShapeItem: L'istanza della forma creata o None se il tipo non è supportato
        """
        if shape_type.lower() == 'rettangolo':
            return RectangleItem(x, y, width, height)
        elif shape_type.lower() in ['ellisse', 'cerchio']:
            return EllipseItem(x, y, width, height)
        elif shape_type.lower() == 'fumetto':
            tail_direction = kwargs.get('tail_direction', 'bottom')
            return BalloonItem(x, y, width, height, tail_direction)
        else:
            print(f"Tipo di forma non supportato: {shape_type}")
            return None
            
    @staticmethod
    def get_available_shapes():
        """
        Restituisce la lista dei tipi di forma disponibili.
        
        Returns:
            list: Lista dei tipi di forma supportati
        """
        return ['Rettangolo', 'Ellisse', 'Cerchio', 'Fumetto']
        
    @staticmethod
    def create_from_dict(data):
        """
        Crea un'istanza di forma a partire da un dizionario.
        
        Args:
            data (dict): Dizionario contenente i dati della forma
            
        Returns:
            ShapeItem: L'istanza della forma creata o None se il tipo non è supportato
        """
        shape_type = data.get('type', '')
        
        if shape_type == 'rectangle':
            return RectangleItem.from_dict(data)
        elif shape_type == 'ellipse':
            return EllipseItem.from_dict(data)
        elif shape_type == 'balloon':
            return BalloonItem.from_dict(data)
        else:
            print(f"Tipo di forma non supportato per caricamento: {shape_type}")
            return None
